import { Connection, PublicKey, Transaction, TransactionInstruction, Ed25519Program,
  SystemProgram, SYSVAR_CLOCK_PUBKEY, SYSVAR_INSTRUCTIONS_PUBKEY } from "@solana/web3.js";
import { Buffer } from "buffer";
import type { CheckoutQuote } from "./rehearsal-checkout";

const TOKEN = new PublicKey("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA");
const ATA = new PublicKey("ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL");
const DEVNET = "EtWTRABZaYq6iMfeYKouRu166VU2xqa1";
const ata = (owner: PublicKey, mint: PublicKey) =>
  PublicKey.findProgramAddressSync([owner.toBuffer(), TOKEN.toBuffer(), mint.toBuffer()], ATA)[0];
function b58(bytes: Uint8Array) {
  const alphabet="123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz";
  let n=0n; for(const b of bytes) n=n*256n+BigInt(b);
  let out=""; while(n){out=alphabet[Number(n%58n)]+out;n/=58n;}
  for(const b of bytes){if(b!==0)break;out="1"+out;} return out;
}
export async function purchaseSignedQuote(q: CheckoutQuote, address: string,
  send: (wire: Uint8Array, kind: "setup" | "purchase") => Promise<Uint8Array>): Promise<string> {
  const connection = new Connection(process.env.NEXT_PUBLIC_SOLANA_RPC_URL || "https://api.devnet.solana.com","confirmed");
  if(await connection.getGenesisHash()!==DEVNET) throw new Error("Expected Solana Devnet");
  if(Date.parse(q.expires_at)<=Date.now()) throw new Error("Quote expired");
  const buyer=new PublicKey(address), mint=new PublicKey(q.mint), program=new PublicKey(q.program_id);
  const config=new PublicKey(q.config_pda), receipt=new PublicKey(q.receipt_pda);
  const message=Buffer.from(q.authorization_message_b64,"base64"), signature=Buffer.from(q.authorization_signature_b64,"base64");
  if(message.length!==462 || signature.length!==64 || !message.subarray(161,193).equals(buyer.toBuffer())
     || !message.subarray(65,97).equals(program.toBuffer()) || !message.subarray(97,129).equals(config.toBuffer())
     || !message.subarray(225,257).equals(mint.toBuffer()) || !message.subarray(257,289).equals(TOKEN.toBuffer())
     || q.decimals!==6 || q.amount_minor_units!==1000000 || message.readBigUInt64LE(289)!==1000000n)
    throw new Error("Invalid quote");
  const count=message[297];
  if(count<1 || count>3 || count!==q.payout_lines.length) throw new Error("Invalid payout count");
  const source=ata(buyer,mint);
  const owners=q.payout_lines.map(p=>new PublicKey(p.wallet));
  const dest=owners.map(o=>ata(o,mint));
  for(let i=0;i<count;i++){
    if(!message.subarray(298+i*40,330+i*40).equals(owners[i].toBuffer())
      || message.readBigUInt64LE(330+i*40)!==BigInt(q.payout_lines[i].amount_minor_units))
      throw new Error("Quote payout mismatch");
  }
  if(q.payout_lines.reduce((a,p)=>a+p.amount_minor_units,0)!==q.amount_minor_units)
    throw new Error("Invalid payout total");
  const [expectedReceipt]=PublicKey.findProgramAddressSync([Buffer.from("purchase_receipt"),message.subarray(129,161)],program);
  if(!expectedReceipt.equals(receipt)) throw new Error("Receipt PDA mismatch");
  const accounts=await connection.getMultipleAccountsInfo([source,...dest],"confirmed");
  if(!accounts[0]) throw new Error("Buyer test token account is missing");
  const setup:TransactionInstruction[]=[];
  for(let i=0;i<count;i++) if(!accounts[i+1]) setup.push(new TransactionInstruction({
    programId:ATA, data:Buffer.from([1]), keys:[
      {pubkey:buyer,isSigner:true,isWritable:true},{pubkey:dest[i],isSigner:false,isWritable:true},
      {pubkey:owners[i],isSigner:false,isWritable:false},{pubkey:mint,isSigner:false,isWritable:false},
      {pubkey:SystemProgram.programId,isSigner:false,isWritable:false},{pubkey:TOKEN,isSigner:false,isWritable:false}
    ]
  }));
  async function submit(ix:TransactionInstruction[], wait:boolean) {
    const block=await connection.getLatestBlockhash("confirmed");
    const tx=new Transaction({feePayer:buyer,recentBlockhash:block.blockhash}).add(...ix);
    const wire=tx.serialize({requireAllSignatures:false,verifySignatures:false});
    if(wire.length>1232) throw new Error("Transaction too large");
    const rawSignature=await send(wire, wait ? "setup" : "purchase");
    if(rawSignature.length!==64) throw new Error("Wallet returned an invalid transaction signature");
    const result=b58(rawSignature);
    if(wait){const status=await connection.confirmTransaction({...block,signature:result},"confirmed");
      if(status.value.err) throw new Error("Token account setup failed");}
    return result;
  }
  if(setup.length) await submit(setup,true);
  if(Date.parse(q.expires_at)<=Date.now()) throw new Error("Quote expired after token account setup");
  const ed=Ed25519Program.createInstructionWithPublicKey({publicKey:new PublicKey(q.signer_pubkey).toBytes(),message,signature});
  const discriminator=new Uint8Array(await crypto.subtle.digest("SHA-256",new TextEncoder().encode("global:purchase"))).slice(0,8);
  const slots=[...dest];while(slots.length<3)slots.push(source);
  const purchase=new TransactionInstruction({programId:program,data:Buffer.from(discriminator),
    keys:[buyer,config,receipt,mint,source,...slots,TOKEN,SystemProgram.programId,SYSVAR_INSTRUCTIONS_PUBKEY,SYSVAR_CLOCK_PUBKEY]
      .map((pubkey,i)=>({pubkey,isSigner:i===0,isWritable:[0,2,4,5,6,7].includes(i)}))});
  return submit([ed,purchase],false);
}
