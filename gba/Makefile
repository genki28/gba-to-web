CC=arm-none-eabi-gcc
all: ../dist/hardware/parade_mb.gba
build:
	mkdir -p build
build/parade.elf: main.c runtime.h font_jp.h start.s multiboot.ld | build
	$(CC) -mcpu=arm7tdmi -marm -Os -ffreestanding -fno-builtin -Wall -Wextra -Werror -Wno-misleading-indentation -nostdlib -Wl,-T,multiboot.ld start.s main.c -o $@
build/parade.bin: build/parade.elf
	arm-none-eabi-objcopy -O binary $< $@
../dist/hardware/parade_mb.gba: build/parade.bin package.py
	mkdir -p $(@D)
	python3 package.py $< $@
