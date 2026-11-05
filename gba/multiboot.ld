ENTRY(_start)
MEMORY { EWRAM (rwx) : ORIGIN = 0x02000000, LENGTH = 256K }
SECTIONS {
    .text : { KEEP(*(.header)) *(.text*) *(.rodata*) } > EWRAM
    .data : { *(.data*) } > EWRAM
    .bss (NOLOAD) : {
        . = ALIGN(4); __bss_start = .;
        *(.bss*) *(COMMON)
        . = ALIGN(4); __bss_end = .;
    } > EWRAM
    /DISCARD/ : { *(.comment) *(.ARM.attributes) }
}
