.syntax unified
.cpu arm7tdmi
.arm
.section .header,"ax"
.global _start
_start:
    b boot
    .space 188
/* Multiboot entry at 0xc0; 0xc4..0xdf reserved for BIOS. */
    b boot
    .space 28
boot:
    mov r0, #0x04000000
    mov r1, #0
    add r0, r0, #0x200
    strh r1, [r0, #8]
    msr cpsr_c, #0xd2
    ldr sp, =0x03007fa0
    msr cpsr_c, #0xdf
    ldr sp, =0x03007f00
    ldr r0, =__bss_start
    ldr r1, =__bss_end
    mov r2, #0
1:  cmp r0, r1
    strlo r2, [r0], #4
    blo 1b
    bl main
2:  b 2b
    .ltorg
