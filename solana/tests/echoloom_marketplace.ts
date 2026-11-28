import * as anchor from "@anchor-lang/core";
import { Program } from "@anchor-lang/core";
import {
  createAccount,
  createAssociatedTokenAccount,
  createAssociatedTokenAccountIdempotent,
  createMint,
  freezeAccount,
  getAccount,
  getAssociatedTokenAddressSync,
  mintTo,
  thawAccount,
} from "@solana/spl-token";
import {
  Ed25519Program,
  Keypair,
  PublicKey,
  sendAndConfirmTransaction,
  SystemProgram,
  Transaction,
  TransactionInstruction,
} from "@solana/web3.js";
import { createHash, randomBytes } from "node:crypto";
import { readFileSync } from "node:fs";
import nacl from "tweetnacl";
import { expect } from "chai";
import { EcholoomMarketplace } from "../target/types/echoloom_marketplace";

const TOKEN_PROGRAM_ID = new PublicKey(
  "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
);
const BOOTSTRAP_PATH = ".local/bootstrap-authority.json";

async function sendBuyerTx(
  connection: anchor.web3.Connection,
  transaction: Transaction,
  payer: Keypair
): Promise<string> {
  transaction.feePayer = payer.publicKey;
  return sendAndConfirmTransaction(connection, transaction, [payer], {
    commitment: "confirmed",
  });
}

function sha256(...parts: Uint8Array[]): Buffer {
  const hash = createHash("sha256");
  parts.forEach((part) => hash.update(part));
  return hash.digest();
}

function orderHash(uuid: Uint8Array): Buffer {
  return sha256(Buffer.from("echoloom:order-ref:v1"), uuid);
}

function signedBytes(args: {
  deploymentDomainHash: ArrayLike<number>;
  config: PublicKey;
  buyer: PublicKey;
  mint: PublicKey;
  orderReferenceHash: ArrayLike<number>;
  productHash: ArrayLike<number>;
  grossAmount: anchor.BN;
  recipientCount: number;
  recipients: { owner: PublicKey; amount: anchor.BN }[];
  configVersion: number;
  expiresAtUnix: anchor.BN;
  nonce: ArrayLike<number>;
  programId: PublicKey;
}): Buffer {
  const padded = [...args.recipients];
  while (padded.length < 3) {
    padded.push({ owner: PublicKey.default, amount: new anchor.BN(0) });
  }
  const parts = [
    sha256(Buffer.from("echoloom:purchase-authorization:v1")),
    Buffer.from([1]),
    Buffer.from(args.deploymentDomainHash),
    args.programId.toBuffer(),
    args.config.toBuffer(),
    Buffer.from(args.orderReferenceHash),
    args.buyer.toBuffer(),
    Buffer.from(args.productHash),
    args.mint.toBuffer(),
    TOKEN_PROGRAM_ID.toBuffer(),
    args.grossAmount.toArrayLike(Buffer, "le", 8),
    Buffer.from([args.recipientCount]),
    ...padded.flatMap((recipient) => [
      recipient.owner.toBuffer(),
      recipient.amount.toArrayLike(Buffer, "le", 8),
    ]),
    Buffer.from(
      Uint8Array.of(
        args.configVersion & 0xff,
        (args.configVersion >>> 8) & 0xff,
        (args.configVersion >>> 16) & 0xff,
        (args.configVersion >>> 24) & 0xff
      )
    ),
    args.expiresAtUnix.toArrayLike(Buffer, "le", 8),
    Buffer.from(args.nonce),
  ];
  const message = Buffer.concat(parts);
  expect(message.length).eq(462);
  return message;
}

type TransactionErrorWithLogs = {
  logs?: string[];
  getLogs?: (connection: anchor.web3.Connection) => Promise<string[] | null>;
};

async function transactionErrorDetails(
  error: unknown,
  connection: anchor.web3.Connection
): Promise<string> {
  const candidate = error as TransactionErrorWithLogs | null;
  let logs = candidate?.logs ?? [];
  if (logs.length === 0 && typeof candidate?.getLogs === "function") {
    try {
      logs = (await candidate.getLogs(connection)) ?? [];
    } catch (logError) {
      logs = [`Could not retrieve transaction logs: ${String(logError)}`];
    }
  }
  return [String(error), ...logs].join("\n");
}

async function fails(
  promise: Promise<unknown>,
  pattern?: RegExp,
  connection?: anchor.web3.Connection
) {
  let failure: unknown;
  try {
    await promise;
  } catch (error) {
    failure = error;
  }
  expect(failure, "expected transaction to fail").not.eq(undefined);
  if (pattern) {
    const details = connection
      ? await transactionErrorDetails(failure, connection)
      : [
          String(failure),
          ...((failure as { logs?: string[] } | undefined)?.logs ?? []),
        ].join("\n");
    expect(details).match(pattern);
  }
}

describe("Echoloom Marketplace local validator", () => {
  // AnchorProvider.env() defaults to "processed", while sendBuyerTx simulates and
  // confirms at "confirmed". Mixing the two makes preflight simulations miss
  // freshly created/frozen accounts and breaks SendTransactionError.getLogs().
  // Use "confirmed" everywhere so setup transactions are visible to preflight.
  const envProvider = anchor.AnchorProvider.env();
  const provider = new anchor.AnchorProvider(
    new anchor.web3.Connection(envProvider.connection.rpcEndpoint, "confirmed"),
    envProvider.wallet,
    { commitment: "confirmed", preflightCommitment: "confirmed" }
  );
  anchor.setProvider(provider);
  const program = anchor.workspace
    .echoloomMarketplace as Program<EcholoomMarketplace>;
  const bootstrap = Keypair.fromSecretKey(
    Uint8Array.from(JSON.parse(readFileSync(BOOTSTRAP_PATH, "utf8")))
  );
  let backendSigner = Keypair.generate();
  const pauseSigner = Keypair.generate();
  const initialPauseSigner = Keypair.generate();
  const mintAuthority = Keypair.generate();
  const freezeAuthority = Keypair.generate();
  const buyer = Keypair.generate();
  const deploymentDomainHash = Buffer.alloc(32, 0x45);
  let mint: PublicKey;
  let config: PublicKey;
  let source: PublicKey;
  let buyerOwner: PublicKey;
  let treasuryOwner: PublicKey;
  let originalTreasuryOwner: PublicKey;
  // Updated by the rotation test; later tests need it to resume after a pause.
  let configAdmin: Keypair = bootstrap;

  it("matches the shared 462-byte cross-language authorization vector", () => {
    const vector = JSON.parse(
      readFileSync("fixtures/authorization-v1.json", "utf8")
    ) as {
      program_id: string;
      config_pda: string;
      deployment_domain_hash_hex: string;
      order_uuid_hex: string;
      order_reference_hash_hex: string;
      buyer: string;
      mint: string;
      product_identifier: string;
      product_hash_hex: string;
      gross_amount: number;
      recipients: { owner: string; amount: number }[];
      recipient_count: number;
      config_version: number;
      expires_at_unix: number;
      nonce_hex: string;
      serialized_message_length: number;
      serialized_message_hex: string;
    };
    const [derivedConfig] = PublicKey.findProgramAddressSync(
      [Buffer.from("marketplace_config")],
      new PublicKey(vector.program_id)
    );
    expect(derivedConfig.toBase58()).eq(vector.config_pda);
    expect(
      orderHash(Buffer.from(vector.order_uuid_hex, "hex")).toString("hex")
    ).eq(vector.order_reference_hash_hex);
    const productBytes = Buffer.from(vector.product_identifier, "utf8");
    const productLength = Buffer.alloc(2);
    productLength.writeUInt16LE(productBytes.length);
    expect(
      sha256(
        Buffer.from("echoloom:product:v1"),
        productLength,
        productBytes
      ).toString("hex")
    ).eq(vector.product_hash_hex);
    const message = signedBytes({
      deploymentDomainHash: Buffer.from(
        vector.deployment_domain_hash_hex,
        "hex"
      ),
      config: derivedConfig,
      buyer: new PublicKey(vector.buyer),
      mint: new PublicKey(vector.mint),
      orderReferenceHash: Buffer.from(vector.order_reference_hash_hex, "hex"),
      productHash: Buffer.from(vector.product_hash_hex, "hex"),
      grossAmount: new anchor.BN(vector.gross_amount),
      recipientCount: vector.recipient_count,
      recipients: vector.recipients.map(({ owner, amount }) => ({
        owner: new PublicKey(owner),
        amount: new anchor.BN(amount),
      })),
      configVersion: vector.config_version,
      expiresAtUnix: new anchor.BN(vector.expires_at_unix),
      nonce: Buffer.from(vector.nonce_hex, "hex"),
      programId: new PublicKey(vector.program_id),
    });
    expect(message.length).eq(vector.serialized_message_length);
    expect(message.toString("hex")).eq(vector.serialized_message_hex);
  });

  before(async () => {
    expect(provider.connection.rpcEndpoint).match(
      /^https?:\/\/(127\.0\.0\.1|localhost):/
    );
    [config] = PublicKey.findProgramAddressSync(
      [Buffer.from("marketplace_config")],
      program.programId
    );
    mint = await createMint(
      provider.connection,
      provider.wallet.payer,
      mintAuthority.publicKey,
      freezeAuthority.publicKey,
      6
    );
    await provider.sendAndConfirm(
      new Transaction().add(
        SystemProgram.transfer({
          fromPubkey: provider.wallet.publicKey,
          toPubkey: buyer.publicKey,
          lamports: 2 * anchor.web3.LAMPORTS_PER_SOL,
        })
      )
    );
    source = await createAssociatedTokenAccount(
      provider.connection,
      provider.wallet.payer,
      mint,
      buyer.publicKey
    );
    buyerOwner = buyer.publicKey;
    await mintTo(
      provider.connection,
      provider.wallet.payer,
      mint,
      source,
      mintAuthority,
      5_000_000_000
    );
  });

  it("prefunds the canonical config PDA and rejects any other bootstrap signer", async () => {
    const rentExempt =
      await provider.connection.getMinimumBalanceForRentExemption(239);
    const prefund = SystemProgram.transfer({
      fromPubkey: provider.wallet.publicKey,
      toPubkey: config,
      lamports: rentExempt,
    });
    await provider.sendAndConfirm(new Transaction().add(prefund));
    const outsider = Keypair.generate();
    const initArgs = {
      platformTreasuryOwner: Keypair.generate().publicKey,
      authorizationSigner: backendSigner.publicKey,
      pauseAuthority: initialPauseSigner.publicKey,
      deploymentDomainHash: Array.from(deploymentDomainHash),
    };
    treasuryOwner = initArgs.platformTreasuryOwner;
    originalTreasuryOwner = treasuryOwner;
    await fails(
      program.methods
        .initializeMarketplace(initArgs)
        .accountsPartial({
          bootstrapAuthority: outsider.publicKey,
          config,
          paymentMint: mint,
          tokenProgram: TOKEN_PROGRAM_ID,
          systemProgram: SystemProgram.programId,
        })
        .signers([outsider])
        .rpc(),
      /InvalidBootstrapAuthority/
    );

    for (const decimals of [5, 9]) {
      const invalidMint = await createMint(
        provider.connection,
        provider.wallet.payer,
        mintAuthority.publicKey,
        freezeAuthority.publicKey,
        decimals
      );
      await fails(
        program.methods
          .initializeMarketplace(initArgs)
          .accountsPartial({
            bootstrapAuthority: bootstrap.publicKey,
            config,
            paymentMint: invalidMint,
            tokenProgram: TOKEN_PROGRAM_ID,
            systemProgram: SystemProgram.programId,
          })
          .signers([bootstrap])
          .rpc(),
        /InvalidMintDecimals/
      );
      const unchanged = await provider.connection.getAccountInfo(config);
      expect(unchanged?.owner.equals(SystemProgram.programId)).eq(true);
      expect(unchanged?.data.length).eq(0);
    }

    await program.methods
      .initializeMarketplace(initArgs)
      .accountsPartial({
        bootstrapAuthority: bootstrap.publicKey,
        config,
        paymentMint: mint,
        tokenProgram: TOKEN_PROGRAM_ID,
        systemProgram: SystemProgram.programId,
      })
      .signers([bootstrap])
      .rpc();

    const data = await provider.connection.getAccountInfo(config);
    expect(data?.data.length).eq(239);
    const stored = await program.account.marketplaceConfig.fetch(config);
    expect(stored.accountVersion).eq(1);
    expect(stored.configVersion).eq(1);
    expect(stored.paused).eq(false);
    expect(stored.authorizationSigner.equals(backendSigner.publicKey)).eq(true);
    expect(stored.paymentMint.equals(mint)).eq(true);
  });

  it("enforces authority rotation and makes pause/resume change the signed config version", async () => {
    const newTreasury = Keypair.generate().publicKey;
    const outsider = Keypair.generate();
    await fails(
      program.methods
        .updateMarketplaceConfig(newTreasury)
        .accountsPartial({ configAuthority: outsider.publicKey, config })
        .signers([outsider])
        .rpc(),
      /Unauthorized/
    );

    await program.methods
      .updateMarketplaceConfig(newTreasury)
      .accountsPartial({ configAuthority: bootstrap.publicKey, config })
      .signers([bootstrap])
      .rpc();
    treasuryOwner = newTreasury;
    expect(
      (await program.account.marketplaceConfig.fetch(config)).configVersion
    ).eq(2);

    const nextBackendSigner = Keypair.generate();
    await program.methods
      .rotateAuthorizedSigner(nextBackendSigner.publicKey)
      .accountsPartial({
        configAuthority: bootstrap.publicKey,
        newSigner: nextBackendSigner.publicKey,
        config,
      })
      .signers([bootstrap, nextBackendSigner])
      .rpc();
    backendSigner = nextBackendSigner;
    await program.methods
      .rotatePauseAuthority(pauseSigner.publicKey)
      .accountsPartial({
        configAuthority: bootstrap.publicKey,
        newAuthority: pauseSigner.publicKey,
        config,
      })
      .signers([bootstrap, pauseSigner])
      .rpc();
    const beforePause = (await program.account.marketplaceConfig.fetch(config))
      .configVersion;
    await program.methods
      .pauseMarketplace()
      .accountsPartial({ pauseAuthority: pauseSigner.publicKey, config })
      .signers([pauseSigner])
      .rpc();
    await program.methods
      .resumeMarketplace()
      .accountsPartial({ configAuthority: bootstrap.publicKey, config })
      .signers([bootstrap])
      .rpc();
    const resumed = await program.account.marketplaceConfig.fetch(config);
    expect(resumed.paused).eq(false);
    expect(resumed.configVersion).eq(beforePause + 2);

    const nextAdmin = Keypair.generate();
    await program.methods
      .rotateConfigAuthority(nextAdmin.publicKey)
      .accountsPartial({
        currentAuthority: bootstrap.publicKey,
        newAuthority: nextAdmin.publicKey,
        config,
      })
      .signers([bootstrap, nextAdmin])
      .rpc();
    configAdmin = nextAdmin;
    await fails(
      program.methods
        .updateMarketplaceConfig(Keypair.generate().publicKey)
        .accountsPartial({ configAuthority: bootstrap.publicKey, config })
        .signers([bootstrap])
        .rpc(),
      /Unauthorized/
    );
  });

  it("executes one authorized payout and stores its durable fixed-size receipt", async () => {
    const recipientOwner = Keypair.generate();
    const recipientAta = await createAssociatedTokenAccount(
      provider.connection,
      provider.wallet.payer,
      mint,
      recipientOwner.publicKey
    );
    const treasuryAta = await createAssociatedTokenAccount(
      provider.connection,
      provider.wallet.payer,
      mint,
      treasuryOwner
    );
    const stored = await program.account.marketplaceConfig.fetch(config);
    expect(stored.platformTreasuryOwner.equals(treasuryOwner)).eq(true);
    const payoutLines = [
      { owner: recipientOwner.publicKey, amount: 900_003 },
      { owner: stored.platformTreasuryOwner, amount: 100_000 },
    ].sort((a, b) => Buffer.compare(a.owner.toBuffer(), b.owner.toBuffer()));
    const destinationByOwner = new Map([
      [recipientOwner.publicKey.toBase58(), recipientAta],
      [stored.platformTreasuryOwner.toBase58(), treasuryAta],
    ]);
    const payoutDestinations = payoutLines.map(
      (line) => destinationByOwner.get(line.owner.toBase58())!
    );
    const uuid = randomBytes(16);
    const orderReferenceHash = orderHash(uuid);
    const [receipt] = PublicKey.findProgramAddressSync(
      [Buffer.from("purchase_receipt"), orderReferenceHash],
      program.programId
    );
    const now = Math.floor(Date.now() / 1000);
    const args = {
      orderReferenceHash: Array.from(orderReferenceHash),
      productHash: Array.from(
        sha256(
          Buffer.from("echoloom:product:v1"),
          Buffer.from([7, 0]),
          Buffer.from("unlock:v1")
        )
      ),
      grossAmount: new anchor.BN(1_000_003),
      recipientCount: payoutLines.length,
      recipients: [
        ...payoutLines.map((line) => ({
          owner: line.owner,
          amount: new anchor.BN(line.amount),
        })),
        { owner: PublicKey.default, amount: new anchor.BN(0) },
      ],
      configVersion: stored.configVersion,
      expiresAtUnix: new anchor.BN(now + 300),
      nonce: Array.from(randomBytes(32)),
    };
    const message = signedBytes({
      ...args,
      deploymentDomainHash,
      config,
      buyer: buyerOwner,
      mint,
      programId: program.programId,
    });
    const ed25519 = Ed25519Program.createInstructionWithPublicKey({
      publicKey: backendSigner.publicKey.toBytes(),
      message,
      signature: nacl.sign.detached(message, backendSigner.secretKey),
    });
    const purchase = await program.methods
      .purchase()
      .accountsPartial({
        buyer: buyer.publicKey,
        config,
        receipt,
        paymentMint: mint,
        buyerSource: source,
        recipient0: payoutDestinations[0],
        recipient1: payoutDestinations[1],
        recipient2: source,
        tokenProgram: TOKEN_PROGRAM_ID,
        systemProgram: SystemProgram.programId,
        instructionsSysvar: anchor.web3.SYSVAR_INSTRUCTIONS_PUBKEY,
        clock: anchor.web3.SYSVAR_CLOCK_PUBKEY,
      })
      .instruction();
    expect(purchase.keys[5].pubkey.equals(payoutDestinations[0])).eq(true);
    expect(purchase.keys[6].pubkey.equals(payoutDestinations[1])).eq(true);
    expect(purchase.keys[7].pubkey.equals(source)).eq(true);
    const recipientInfo = await provider.connection.getAccountInfo(
      recipientAta
    );
    expect(recipientInfo?.owner.equals(TOKEN_PROGRAM_ID)).eq(true);
    const recipientToken = await getAccount(provider.connection, recipientAta);
    expect(recipientToken.owner.equals(recipientOwner.publicKey)).eq(true);
    expect(recipientToken.mint.equals(mint)).eq(true);
    expect(recipientToken.isFrozen).eq(false);
    const tx = new Transaction().add(ed25519, purchase);
    await sendBuyerTx(provider.connection, tx, buyer);

    const receiptInfo = await provider.connection.getAccountInfo(receipt);
    expect(receiptInfo?.data.length).eq(287);
    expect(receiptInfo?.owner.equals(program.programId)).eq(true);
    const receiptData = receiptInfo!.data;
    expect(
      receiptData
        .subarray(0, 8)
        .equals(sha256(Buffer.from("account:PurchaseReceipt")).subarray(0, 8))
    ).eq(true);
    expect(receiptData[8]).eq(1);
    expect(receiptData.subarray(10, 42).equals(buyer.publicKey.toBuffer())).eq(
      true
    );
    expect(receiptData.subarray(42, 74).equals(orderReferenceHash)).eq(true);
    expect(receiptData.readBigUInt64LE(138)).eq(BigInt(1_000_003));
    expect(receiptData[146]).eq(2);
    payoutLines.forEach((line, index) => {
      const offset = 147 + index * 40;
      expect(
        receiptData.subarray(offset, offset + 32).equals(line.owner.toBuffer())
      ).eq(true);
      expect(receiptData.readBigUInt64LE(offset + 32)).eq(BigInt(line.amount));
    });
    expect(
      await provider.connection
        .getTokenAccountBalance(recipientAta)
        .then((b) => b.value.amount)
    ).eq("900003");
    expect(
      await provider.connection
        .getTokenAccountBalance(treasuryAta)
        .then((b) => b.value.amount)
    ).eq("100000");
    await fails(
      sendBuyerTx(
        provider.connection,
        new Transaction().add(ed25519, purchase),
        buyer
      ),
      /PurchaseAlreadyProcessed|already been processed/
    );
  });

  it("rolls back earlier payouts and leaves the receipt uncreated when a later payout fails", async () => {
    const owners = [
      treasuryOwner,
      Keypair.generate().publicKey,
      Keypair.generate().publicKey,
    ].sort((a, b) => Buffer.compare(a.toBuffer(), b.toBuffer()));
    const destinations: PublicKey[] = [];
    for (const owner of owners) {
      destinations.push(
        await createAssociatedTokenAccountIdempotent(
          provider.connection,
          provider.wallet.payer,
          mint,
          owner
        )
      );
    }
    const configState = await program.account.marketplaceConfig.fetch(config);
    const orderReferenceHash = orderHash(randomBytes(16));
    const [receipt] = PublicKey.findProgramAddressSync(
      [Buffer.from("purchase_receipt"), orderReferenceHash],
      program.programId
    );
    const payoutAmounts = [101_001, 202_002, 303_003];
    const gross = payoutAmounts.reduce((sum, amount) => sum + amount, 0);
    const now = Math.floor(Date.now() / 1000);
    const args = {
      orderReferenceHash: Array.from(orderReferenceHash),
      productHash: Array.from(sha256(Buffer.from("integration-product"))),
      grossAmount: new anchor.BN(gross),
      recipientCount: 3,
      recipients: owners.map((owner, i) => ({
        owner,
        amount: new anchor.BN(payoutAmounts[i]),
      })),
      configVersion: configState.configVersion,
      expiresAtUnix: new anchor.BN(now + 300),
      nonce: Array.from(randomBytes(32)),
    };
    const message = signedBytes({
      ...args,
      deploymentDomainHash,
      config,
      buyer: buyer.publicKey,
      mint,
      programId: program.programId,
    });
    const ed25519 = Ed25519Program.createInstructionWithPublicKey({
      publicKey: backendSigner.publicKey.toBytes(),
      message,
      signature: nacl.sign.detached(message, backendSigner.secretKey),
    });
    const purchase = await program.methods
      .purchase()
      .accountsPartial({
        buyer: buyer.publicKey,
        config,
        receipt,
        paymentMint: mint,
        buyerSource: source,
        recipient0: destinations[0],
        recipient1: destinations[1],
        recipient2: destinations[2],
        tokenProgram: TOKEN_PROGRAM_ID,
        systemProgram: SystemProgram.programId,
        instructionsSysvar: anchor.web3.SYSVAR_INSTRUCTIONS_PUBKEY,
        clock: anchor.web3.SYSVAR_CLOCK_PUBKEY,
      })
      .instruction();
    expect(purchase.keys[5].pubkey.equals(destinations[0])).eq(true);
    expect(purchase.keys[6].pubkey.equals(destinations[1])).eq(true);
    expect(purchase.keys[7].pubkey.equals(destinations[2])).eq(true);
    const beforeBuyer = await provider.connection.getTokenAccountBalance(
      source
    );
    const beforeRecipients = await Promise.all(
      destinations.map((destination) =>
        provider.connection.getTokenAccountBalance(destination)
      )
    );

    // Fail the second payout deliberately: the first payout must be rolled back.
    // This matches the observed execution order (one TransferChecked succeeds,
    // then the frozen recipient rejects the next TransferChecked).
    const failingRecipientIndex = 1;
    const failingDestination = destinations[failingRecipientIndex];
    await freezeAccount(
      provider.connection,
      provider.wallet.payer,
      failingDestination,
      mint,
      freezeAuthority
    );
    expect(
      (await getAccount(provider.connection, failingDestination)).isFrozen
    ).eq(true);
    await fails(
      sendBuyerTx(
        provider.connection,
        new Transaction().add(ed25519, purchase),
        buyer
      ),
      /Account is frozen|custom program error: 0x11\b|"Custom":\s*17\b/i,
      provider.connection
    );
    console.log(
      "[atomic-rollback] Expected frozen-recipient failure was observed."
    );
    expect(await provider.connection.getAccountInfo(receipt)).eq(null);
    expect(
      (await provider.connection.getTokenAccountBalance(source)).value.amount
    ).eq(beforeBuyer.value.amount);
    const afterFailure = await Promise.all(
      destinations.map((destination) =>
        provider.connection.getTokenAccountBalance(destination)
      )
    );
    afterFailure.forEach((balance, index) =>
      expect(balance.value.amount).eq(beforeRecipients[index].value.amount)
    );

    await thawAccount(
      provider.connection,
      provider.wallet.payer,
      failingDestination,
      mint,
      freezeAuthority
    );
    expect(
      (await getAccount(provider.connection, failingDestination)).isFrozen
    ).eq(false);
    const thawedStates = await Promise.all(
      destinations.map(
        async (account) =>
          (
            await getAccount(provider.connection, account)
          ).isFrozen
      )
    );
    expect(thawedStates).deep.eq([false, false, false]);
    console.log(
      "[atomic-rollback] All recipient accounts are thawed; checking retry."
    );
    const retryPurchase = await program.methods
      .purchase()
      .accountsPartial({
        buyer: buyer.publicKey,
        config,
        receipt,
        paymentMint: mint,
        buyerSource: source,
        recipient0: destinations[0],
        recipient1: destinations[1],
        recipient2: destinations[2],
        tokenProgram: TOKEN_PROGRAM_ID,
        systemProgram: SystemProgram.programId,
        instructionsSysvar: anchor.web3.SYSVAR_INSTRUCTIONS_PUBKEY,
        clock: anchor.web3.SYSVAR_CLOCK_PUBKEY,
      })
      .instruction();
    // A failed Solana transaction does not consume the receipt PDA, but the
    // backend may issue a fresh authorization before the buyer retries. Keep
    // the same order and payout terms while refreshing expiry and nonce.
    const retryArgs = {
      ...args,
      expiresAtUnix: new anchor.BN(Math.floor(Date.now() / 1000) + 600),
      nonce: Array.from(randomBytes(32)),
    };
    const retryMessage = signedBytes({
      ...retryArgs,
      deploymentDomainHash,
      config,
      buyer: buyer.publicKey,
      mint,
      programId: program.programId,
    });
    const retryEd25519 = Ed25519Program.createInstructionWithPublicKey({
      publicKey: backendSigner.publicKey.toBytes(),
      message: retryMessage,
      signature: nacl.sign.detached(retryMessage, backendSigner.secretKey),
    });
    try {
      await sendBuyerTx(
        provider.connection,
        new Transaction().add(retryEd25519, retryPurchase),
        buyer
      );
    } catch (error) {
      const details = await transactionErrorDetails(error, provider.connection);
      throw new Error(
        `Retry after thawing the frozen recipient failed:\n${details}`
      );
    }
    console.log(
      "[atomic-rollback] Retry succeeded with a fresh authorization."
    );
    expect(
      (await provider.connection.getTokenAccountBalance(source)).value.amount
    ).eq((BigInt(beforeBuyer.value.amount) - BigInt(gross)).toString());
    expect(await provider.connection.getAccountInfo(receipt)).not.eq(null);
    const afterRetry = await Promise.all(
      destinations.map((destination) =>
        provider.connection.getTokenAccountBalance(destination)
      )
    );
    afterRetry.forEach((balance, index) =>
      expect(
        BigInt(balance.value.amount) -
          BigInt(beforeRecipients[index].value.amount)
      ).eq(BigInt(payoutAmounts[index]))
    );
  });

  it("rejects purchase invoked through a separate test-only CPI wrapper", async () => {
    const wrapper = Keypair.fromSecretKey(
      Uint8Array.from(
        JSON.parse(readFileSync(".local/cpi-wrapper-keypair.json", "utf8"))
      )
    );
    const recipient = Keypair.generate();
    const destination = await createAssociatedTokenAccount(
      provider.connection,
      provider.wallet.payer,
      mint,
      recipient.publicKey
    );
    const currentConfig = await program.account.marketplaceConfig.fetch(config);
    const orderReferenceHash = orderHash(randomBytes(16));
    const [receipt] = PublicKey.findProgramAddressSync(
      [Buffer.from("purchase_receipt"), orderReferenceHash],
      program.programId
    );
    const now = Math.floor(Date.now() / 1000);
    const args = {
      orderReferenceHash: Array.from(orderReferenceHash),
      productHash: Array.from(sha256(Buffer.from("cpi-test-product"))),
      grossAmount: new anchor.BN(77_777),
      recipientCount: 1,
      recipients: [
        { owner: recipient.publicKey, amount: new anchor.BN(77_777) },
        { owner: PublicKey.default, amount: new anchor.BN(0) },
        { owner: PublicKey.default, amount: new anchor.BN(0) },
      ],
      configVersion: currentConfig.configVersion,
      expiresAtUnix: new anchor.BN(now + 300),
      nonce: Array.from(randomBytes(32)),
    };
    const message = signedBytes({
      ...args,
      deploymentDomainHash,
      config,
      buyer: buyer.publicKey,
      mint,
      programId: program.programId,
    });
    const ed25519 = Ed25519Program.createInstructionWithPublicKey({
      publicKey: backendSigner.publicKey.toBytes(),
      message,
      signature: nacl.sign.detached(message, backendSigner.secretKey),
    });
    const purchase = await program.methods
      .purchase()
      .accountsPartial({
        buyer: buyer.publicKey,
        config,
        receipt,
        paymentMint: mint,
        buyerSource: source,
        recipient0: destination,
        recipient1: source,
        recipient2: source,
        tokenProgram: TOKEN_PROGRAM_ID,
        systemProgram: SystemProgram.programId,
        instructionsSysvar: anchor.web3.SYSVAR_INSTRUCTIONS_PUBKEY,
        clock: anchor.web3.SYSVAR_CLOCK_PUBKEY,
      })
      .instruction();
    const cpi = new TransactionInstruction({
      programId: wrapper.publicKey,
      keys: [
        { pubkey: program.programId, isSigner: false, isWritable: false },
        ...purchase.keys,
      ],
      data: purchase.data,
    });
    const before = await provider.connection.getTokenAccountBalance(source);
    await fails(
      sendBuyerTx(
        provider.connection,
        new Transaction().add(ed25519, cpi),
        buyer
      ),
      /InvalidInstructionStackHeight|stack height/i
    );
    expect(await provider.connection.getAccountInfo(receipt)).eq(null);
    expect(
      (await provider.connection.getTokenAccountBalance(source)).value.amount
    ).eq(before.value.amount);
  });
  describe("purchase rejects invalid authorizations, accounts and payouts", () => {
    type Line = { owner: PublicKey; amount: number };
    type Overrides = {
      signer?: Keypair;
      messageBuyer?: PublicKey;
      messageMint?: PublicKey;
      lines?: Line[];
      destinations?: PublicKey[];
      grossAmount?: number;
      expiresIn?: number;
      configVersion?: number;
      paymentMint?: PublicKey;
      buyerSource?: PublicKey;
      omitEd25519?: boolean;
      between?: TransactionInstruction[];
      tamperSignedMessage?: boolean;
    };
    type Recipient = { owner: PublicKey; ata: PublicKey };
    let recipients: Recipient[] = [];
    let attacker: Recipient;
    let otherMint: PublicKey;
    let nonCanonical: PublicKey;

    async function makeRecipient(owner: PublicKey): Promise<Recipient> {
      const ata = await createAssociatedTokenAccount(
        provider.connection,
        provider.wallet.payer,
        mint,
        owner
      );
      return { owner, ata };
    }

    async function tokenAmount(account: PublicKey): Promise<bigint> {
      const balance = await provider.connection.getTokenAccountBalance(account);
      return BigInt(balance.value.amount);
    }

    async function buildPurchase(o: Overrides = {}) {
      const state = await program.account.marketplaceConfig.fetch(config);
      const lines: Line[] =
        o.lines ??
        [
          { owner: recipients[0].owner, amount: 900_000 },
          { owner: state.platformTreasuryOwner, amount: 100_000 },
        ].sort((a, b) =>
          Buffer.compare(a.owner.toBuffer(), b.owner.toBuffer())
        );
      const gross =
        o.grossAmount ?? lines.reduce((sum, line) => sum + line.amount, 0);
      const orderReferenceHash = orderHash(randomBytes(16));
      const [receipt] = PublicKey.findProgramAddressSync(
        [Buffer.from("purchase_receipt"), orderReferenceHash],
        program.programId
      );
      const now = Math.floor(Date.now() / 1000);
      const message = signedBytes({
        deploymentDomainHash,
        config,
        buyer: o.messageBuyer ?? buyer.publicKey,
        mint: o.messageMint ?? mint,
        orderReferenceHash,
        productHash: sha256(Buffer.from("negative-case-product")),
        grossAmount: new anchor.BN(gross),
        recipientCount: lines.length,
        recipients: lines.map((line) => ({
          owner: line.owner,
          amount: new anchor.BN(line.amount),
        })),
        configVersion: o.configVersion ?? state.configVersion,
        expiresAtUnix: new anchor.BN(now + (o.expiresIn ?? 300)),
        nonce: randomBytes(32),
        programId: program.programId,
      });
      const signer = o.signer ?? backendSigner;
      const signature = nacl.sign.detached(message, signer.secretKey);
      const embedded = o.tamperSignedMessage
        ? Buffer.concat([
            message.subarray(0, message.length - 1),
            Buffer.from([message[message.length - 1] ^ 1]),
          ])
        : message;
      const ed25519 = Ed25519Program.createInstructionWithPublicKey({
        publicKey: signer.publicKey.toBytes(),
        message: embedded,
        signature,
      });
      const destinations = [
        ...(o.destinations ??
          lines.map((line) => getAssociatedTokenAddressSync(mint, line.owner))),
      ];
      while (destinations.length < 3) {
        destinations.push(source);
      }
      const purchase = await program.methods
        .purchase()
        .accountsPartial({
          buyer: buyer.publicKey,
          config,
          receipt,
          paymentMint: o.paymentMint ?? mint,
          buyerSource: o.buyerSource ?? source,
          recipient0: destinations[0],
          recipient1: destinations[1],
          recipient2: destinations[2],
          tokenProgram: TOKEN_PROGRAM_ID,
          systemProgram: SystemProgram.programId,
          instructionsSysvar: anchor.web3.SYSVAR_INSTRUCTIONS_PUBKEY,
          clock: anchor.web3.SYSVAR_CLOCK_PUBKEY,
        })
        .instruction();
      const instructions: TransactionInstruction[] = [];
      if (!o.omitEd25519) {
        instructions.push(ed25519);
      }
      instructions.push(...(o.between ?? []), purchase);
      return { transaction: new Transaction().add(...instructions), receipt };
    }

    // A rejected purchase must leave no receipt and no token movement.
    async function expectRejected(o: Overrides, pattern?: RegExp) {
      const beforeBuyer = await tokenAmount(source);
      const beforeRecipient = await tokenAmount(recipients[0].ata);
      const state = await program.account.marketplaceConfig.fetch(config);
      const treasuryAta = getAssociatedTokenAddressSync(
        mint,
        state.platformTreasuryOwner
      );
      const beforeTreasury = await tokenAmount(treasuryAta);
      const { transaction, receipt } = await buildPurchase(o);
      await fails(
        sendBuyerTx(provider.connection, transaction, buyer),
        pattern,
        provider.connection
      );
      expect(await provider.connection.getAccountInfo(receipt)).eq(null);
      expect(await tokenAmount(source)).eq(beforeBuyer);
      expect(await tokenAmount(recipients[0].ata)).eq(beforeRecipient);
      expect(await tokenAmount(treasuryAta)).eq(beforeTreasury);
    }

    before(async () => {
      const owners = [
        Keypair.generate().publicKey,
        Keypair.generate().publicKey,
        Keypair.generate().publicKey,
      ].sort((a, b) => Buffer.compare(a.toBuffer(), b.toBuffer()));
      recipients = [];
      for (const owner of owners) {
        recipients.push(await makeRecipient(owner));
      }
      attacker = await makeRecipient(Keypair.generate().publicKey);
      otherMint = await createMint(
        provider.connection,
        provider.wallet.payer,
        mintAuthority.publicKey,
        null,
        6
      );
      // A second token account of the first recipient that is not its ATA.
      nonCanonical = await createAccount(
        provider.connection,
        provider.wallet.payer,
        mint,
        recipients[0].owner,
        Keypair.generate()
      );
    });

    it("rejects an authorization signed by a key other than the configured signer", async () => {
      await expectRejected(
        { signer: Keypair.generate() },
        /InvalidAuthorizationSigner/
      );
    });

    it("rejects a purchase with no Ed25519 instruction before it", async () => {
      await expectRejected(
        { omitEd25519: true },
        /InvalidAuthorizationInstruction/
      );
    });

    it("rejects an Ed25519 instruction that is not immediately before purchase", async () => {
      const filler = SystemProgram.transfer({
        fromPubkey: buyer.publicKey,
        toPubkey: provider.wallet.publicKey,
        lamports: 1,
      });
      await expectRejected(
        { between: [filler] },
        /InvalidAuthorizationInstruction/
      );
    });

    it("rejects a message that differs from the one the signer signed", async () => {
      await expectRejected({ tamperSignedMessage: true });
    });

    it("rejects an expired authorization", async () => {
      await expectRejected({ expiresIn: -120 }, /ExpiredAuthorization/);
    });

    it("rejects an authorization valid for longer than the 1800 second cap", async () => {
      await expectRejected(
        { expiresIn: 3600 },
        /AuthorizationLifetimeExceeded/
      );
    });

    it("accepts an authorization valid for 25 minutes", async () => {
      const amount = 500_000;
      const configState = await program.account.marketplaceConfig.fetch(config);
      const successfulLines = [
        { owner: recipients[0].owner, amount: 450_000 },
        { owner: configState.platformTreasuryOwner, amount: 50_000 },
      ].sort((a, b) => Buffer.compare(a.owner.toBuffer(), b.owner.toBuffer()));
      const beforeBuyer = await tokenAmount(source);
      const beforeRecipient = await tokenAmount(recipients[0].ata);
      const { transaction, receipt } = await buildPurchase({
        lines: successfulLines,
        expiresIn: 1500,
      });
      await sendBuyerTx(provider.connection, transaction, buyer);
      expect(
        (await provider.connection.getAccountInfo(receipt))?.data.length
      ).eq(287);
      expect(await tokenAmount(source)).eq(beforeBuyer - BigInt(amount));
      expect(await tokenAmount(recipients[0].ata)).eq(
        beforeRecipient + BigInt(450_000)
      );
    });

    it("rejects otherwise valid payouts that omit the configured treasury", async () => {
      await expectRejected(
        { lines: [{ owner: recipients[0].owner, amount: 1_000_000 }] },
        /MissingTreasuryPayout/
      );
    });

    it("rejects a zero treasury payout with the existing positive-amount error", async () => {
      const state = await program.account.marketplaceConfig.fetch(config);
      const lines = [
        { owner: recipients[0].owner, amount: 1_000_000 },
        { owner: state.platformTreasuryOwner, amount: 0 },
      ].sort((a, b) => Buffer.compare(a.owner.toBuffer(), b.owner.toBuffer()));
      await expectRejected({ lines }, /InvalidPayoutAmounts/);
    });

    it("requires the current treasury owner after a treasury update", async () => {
      const state = await program.account.marketplaceConfig.fetch(config);
      expect(state.platformTreasuryOwner.equals(treasuryOwner)).eq(true);
      expect(state.platformTreasuryOwner.equals(originalTreasuryOwner)).eq(
        false
      );
      const oldTreasury = await makeRecipient(originalTreasuryOwner);
      const lines = [
        { owner: recipients[0].owner, amount: 900_000 },
        { owner: oldTreasury.owner, amount: 100_000 },
      ].sort((a, b) => Buffer.compare(a.owner.toBuffer(), b.owner.toBuffer()));
      await expectRejected(
        {
          lines,
          destinations: lines.map((line) =>
            line.owner.equals(oldTreasury.owner)
              ? oldTreasury.ata
              : recipients[0].ata
          ),
        },
        /MissingTreasuryPayout/
      );
    });

    it("validates the treasury payout destination as its canonical token account", async () => {
      const state = await program.account.marketplaceConfig.fetch(config);
      const lines = [
        { owner: recipients[0].owner, amount: 500_000 },
        { owner: state.platformTreasuryOwner, amount: 500_000 },
      ].sort((a, b) => Buffer.compare(a.owner.toBuffer(), b.owner.toBuffer()));
      const destinations = lines.map((line) =>
        line.owner.equals(state.platformTreasuryOwner)
          ? attacker.ata
          : recipients[0].ata
      );
      await expectRejected({ lines, destinations }, /InvalidRecipientAccount/);
    });

    it("rejects a purchase whose signed buyer differs from the transaction buyer", async () => {
      await expectRejected(
        { messageBuyer: Keypair.generate().publicKey },
        /InvalidBuyer\b/
      );
    });

    it("rejects a buyer source token account the buyer does not own", async () => {
      await expectRejected(
        { buyerSource: recipients[1].ata },
        /InvalidBuyerTokenAccount/
      );
    });

    it("rejects a signed mint that differs from the configured mint", async () => {
      await expectRejected({ messageMint: otherMint }, /InvalidMint/);
    });

    it("rejects a payment mint account that differs from the configured mint", async () => {
      await expectRejected(
        { paymentMint: otherMint },
        /ConstraintAddress|address constraint/i
      );
    });

    it("rejects recipients that are not sorted by public key bytes", async () => {
      await expectRejected(
        {
          lines: [
            { owner: recipients[1].owner, amount: 400_000 },
            { owner: recipients[0].owner, amount: 600_000 },
          ],
        },
        /UnsortedRecipients/
      );
    });

    it("rejects duplicate recipients", async () => {
      await expectRejected(
        {
          lines: [
            { owner: recipients[0].owner, amount: 400_000 },
            { owner: recipients[0].owner, amount: 600_000 },
          ],
        },
        /DuplicateRecipient/
      );
    });

    it("rejects the buyer as a payout recipient", async () => {
      await expectRejected(
        {
          lines: [{ owner: buyer.publicKey, amount: 1_000_000 }],
          destinations: [source],
        },
        /BuyerCannotReceivePayout/
      );
    });

    it("rejects payouts that do not add up to the signed gross amount", async () => {
      await expectRejected(
        {
          lines: [{ owner: recipients[0].owner, amount: 1_000_000 }],
          grossAmount: 1_000_001,
        },
        /InvalidTotalAmount/
      );
    });

    it("rejects a recipient token account owned by someone else", async () => {
      await expectRejected(
        { destinations: [attacker.ata] },
        /InvalidRecipientAccount/
      );
    });

    it("rejects a non-canonical token account of the right recipient", async () => {
      await expectRejected(
        { destinations: [nonCanonical] },
        /InvalidRecipientAccount/
      );
    });

    it("rejects an unused recipient slot that is not the buyer source sentinel", async () => {
      const lines = [{ owner: recipients[0].owner, amount: 1_000_000 }];
      await expectRejected(
        { lines, destinations: [recipients[0].ata, recipients[1].ata] },
        /InvalidRecipientAccount/
      );
    });

    it("rejects purchases while the marketplace is paused", async () => {
      await program.methods
        .pauseMarketplace()
        .accountsPartial({ pauseAuthority: pauseSigner.publicKey, config })
        .signers([pauseSigner])
        .rpc();
      try {
        await expectRejected({}, /MarketplacePaused/);
      } finally {
        await program.methods
          .resumeMarketplace()
          .accountsPartial({ configAuthority: configAdmin.publicKey, config })
          .signers([configAdmin])
          .rpc();
      }
    });

    it("rejects an authorization signed for a config version that pause/resume replaced", async () => {
      const staleVersion = (
        await program.account.marketplaceConfig.fetch(config)
      ).configVersion;
      await program.methods
        .pauseMarketplace()
        .accountsPartial({ pauseAuthority: pauseSigner.publicKey, config })
        .signers([pauseSigner])
        .rpc();
      await program.methods
        .resumeMarketplace()
        .accountsPartial({ configAuthority: configAdmin.publicKey, config })
        .signers([configAdmin])
        .rpc();
      await expectRejected(
        { configVersion: staleVersion },
        /InvalidAuthorization\b/
      );
    });
  });
});
