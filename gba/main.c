#include <stdint.h>
#define REG16(a) (*(volatile uint16_t *)(a))
#ifdef HOST_TEST
static uint16_t screen_buffer[240*160];
#define SCREEN screen_buffer
#else
#define SCREEN ((volatile uint16_t *)0x06000000)
#endif
static const uint8_t font[26][7] = {
 {14,17,17,31,17,17,17}, {30,17,17,30,17,17,30},
 {14,17,16,16,16,17,14}, {30,17,17,17,17,17,30},
 {31,16,16,30,16,16,31}, {31,16,16,30,16,16,16},
 {14,17,16,23,17,17,14}, {17,17,17,31,17,17,17},
 {31,4,4,4,4,4,31}, {7,2,2,2,18,18,12},
 {17,18,20,24,20,18,17}, {16,16,16,16,16,16,31},
 {17,27,21,21,17,17,17}, {17,25,21,19,17,17,17},
 {14,17,17,17,17,17,14}, {30,17,17,30,16,16,16},
 {14,17,17,17,21,18,13}, {30,17,17,30,20,18,17},
 {15,16,16,14,1,1,30}, {31,4,4,4,4,4,4},
 {17,17,17,17,17,17,14}, {17,17,17,17,17,10,4},
 {17,17,17,21,21,21,10}, {17,17,10,4,10,17,17},
 {17,17,10,4,4,4,4}, {31,1,2,4,8,16,31}
};

#define RGB(r,g,b) ((r) | ((g)<<5) | ((b)<<10))
static void rect(int x, int y, int w, int h, uint16_t color) {
    for (int row = y; row < y+h; ++row)
        for (int col = x; col < x+w; ++col)
            if ((unsigned)col < 240 && (unsigned)row < 160)
                SCREEN[row*240+col] = color;
}
static void text(int x, int y, const char *s, int scale, uint16_t color) {
    for (; *s; ++s, x += 6*scale) {
        if (*s < 'A' || *s > 'Z') continue;
        for (int row=0; row<7; ++row)
            for (int col=0; col<5; ++col)
                if (font[*s-'A'][row] & (1u << (4-col)))
                    rect(x+col*scale, y+row*scale, scale, scale, color);
    }
}

#include "font_jp.h"
#include "runtime.h"
/* One scanline per main-loop pass: serial polling continues during drawing. */
static void draw_step(void){
 if(!rendering)return;
 unsigned row=render_row,base=(row>>4)*13,gy=row&15;
 for(unsigned cell=0;cell<13;cell++){
  unsigned i=base+cell;int glyph=i<message_length?glyph_index(message[i]):-1;
  uint16_t bits=glyph<0?0:jp_rows[glyph][gy];
  for(unsigned x=0;x<16;x++)SCREEN[(40+row)*240+16+cell*16+x]=(bits&(1u<<(15-x)))?RGB(27,31,29):RGB(3,7,11);
 }
 if(++render_row==80){rendering=0;ack_id=draw_id;ack_crc=draw_crc;ack_valid=1;}
}
static void draw_screen(void){
 rect(0,0,240,160,RGB(2,4,7));text(16,12,"GBA WEB CUE",2,RGB(15,31,22));
 text(16,30,"JAPANESE NOTES",1,RGB(20,24,28));rect(16,40,208,80,RGB(3,7,11));
 text(16,134,"A RIGHT NEXT",1,RGB(20,24,28));text(16,148,"B LEFT PREV",1,RGB(20,24,28));
}
#ifndef HOST_TEST
int main(void){
 REG16(0x04000000)=0x0483;REG16(0x04000020)=256;REG16(0x04000022)=0;REG16(0x04000024)=0;REG16(0x04000026)=256;
 REG16(0x04000028)=0;REG16(0x0400002a)=0;REG16(0x0400002c)=0;REG16(0x0400002e)=0;REG16(0x04000050)=0;
 draw_screen();text(20,70,"WAITING FOR WEB",1,RGB(27,31,29));REG16(0x04000000)=0x0403;
 REG16(0x04000208)=0;REG16(0x04000134)=0;REG16(0x04000128)=0x6003;REG16(0x0400012a)=0xd302;REG16(0x04000202)=0x80;
 for(;;){if(REG16(0x04000202)&0x80){unsigned w=REG16(0x04000120);REG16(0x04000202)=0x80;receive(w);REG16(0x0400012a)=next_word((~REG16(0x04000130))&1023);}draw_step();}
}
#endif
