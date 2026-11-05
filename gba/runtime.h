/* Application protocol v2. Independent of USB/adapter firmware. */
#define MAX_CHARS 65
static uint16_t stage[MAX_CHARS],message[MAX_CHARS];
static unsigned phase,count,got,sum,frame_type,words[29];
static uint32_t stage_id,draw_id,ack_id;
static unsigned stage_total,stage_have,message_length,render_row,rendering,ack_valid,txpos;
static uint16_t draw_crc,ack_crc;
static uint16_t crc_word(uint16_t crc,uint16_t w){
 for(unsigned j=0;j<2;j++){crc^=(uint16_t)((w&255)<<8);w>>=8;for(unsigned i=0;i<8;i++)crc=(uint16_t)((crc<<1)^((crc&0x8000)?0x1021:0));}return crc;
}
static uint16_t text_crc(uint32_t id,unsigned total,const uint16_t *s){uint16_t crc=crc_word(0xffff,(uint16_t)id);crc=crc_word(crc,(uint16_t)(id>>16));crc=crc_word(crc,(uint16_t)total);for(unsigned i=0;i<total;i++)crc=crc_word(crc,s[i]);return crc;}
static int glyph_index(unsigned code){int lo=0,hi=JP_GLYPH_COUNT-1;while(lo<=hi){int mid=(lo+hi)>>1;if(jp_codes[mid]==code)return mid;if(jp_codes[mid]<code)lo=mid+1;else hi=mid-1;}return -1;}
static void accept_frame(void){
 if(frame_type==0x22&&count>=5){
  uint32_t id=(uint32_t)words[0]|((uint32_t)words[1]<<16);unsigned offset=words[2],total=words[3],n=count-4;
  if(!id||!total||total>MAX_CHARS||offset+n>total)return;
  for(unsigned i=4;i<count;i++)if(glyph_index(words[i])<0)return;
  if(id!=stage_id){if(offset)return;stage_id=id;stage_total=total;stage_have=0;}
  if(total!=stage_total||offset>stage_have)return;
  if(offset<stage_have){if(offset+n>stage_have)return;for(unsigned i=0;i<n;i++)if(stage[offset+i]!=words[4+i])return;return;}
  for(unsigned i=0;i<n;i++)stage[offset+i]=(uint16_t)words[4+i];stage_have+=n;
 }else if(frame_type==0x23&&count==3){
  uint32_t id=(uint32_t)words[0]|((uint32_t)words[1]<<16);uint16_t crc=(uint16_t)words[2];
  if(!id||!stage_total||id!=stage_id||stage_have!=stage_total||crc!=text_crc(id,stage_total,stage))return;
  if((ack_valid&&id==ack_id&&crc==ack_crc)||(rendering&&id==draw_id&&crc==draw_crc))return;
  for(unsigned i=0;i<stage_total;i++)message[i]=stage[i];message_length=stage_total;draw_id=id;draw_crc=crc;
  render_row=0;rendering=1;
 }
}
static void receive(unsigned w){
 if(!phase){if(w==0xa55a)phase=1;return;}
 if(phase==1){count=w&255;got=0;sum=w;frame_type=w>>8;if(count>29||(frame_type!=0x22&&frame_type!=0x23)){phase=0;return;}phase=count?2:3;return;}
 if(phase==2){words[got++]=w;sum+=w;if(got==count)phase=3;return;}
 phase=0;if(((sum+w)&65535)==0)accept_frame();
}
/* Receipts persist and repeat. Snapshot an entire ACK frame so a newly
 * completed draw cannot mix transaction IDs in a partially sent receipt. */
static uint16_t ack_frame[6];
static unsigned ack_pos;
static uint16_t next_word(unsigned keys){
 if(ack_pos){uint16_t w=ack_frame[ack_pos++];if(ack_pos==6)ack_pos=0;return w;}
 unsigned slot=txpos++&7;
 if(slot==0)return 0xd302;
 if(slot==2&&ack_valid){ack_frame[0]=0xa55a;ack_frame[1]=0x3103;ack_frame[2]=(uint16_t)ack_id;ack_frame[3]=(uint16_t)(ack_id>>16);ack_frame[4]=ack_crc;ack_frame[5]=(uint16_t)(-(ack_frame[1]+ack_frame[2]+ack_frame[3]+ack_frame[4]));ack_pos=1;return ack_frame[0];}
 return (uint16_t)(0xb000|(keys&1023));
}
