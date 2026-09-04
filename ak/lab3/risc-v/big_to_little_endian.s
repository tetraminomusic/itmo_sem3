        .data

    input_addr:     .word 0x80
    output_addr:    .word 0x84
    stack_top:      .word 0x1000

        .text
        .org 0x100
    
_start:

                                            ; Инициализируем стек
    lui         t0, %hi(stack_top)
    addi        t0, t0, %lo(stack_top)
    lw          sp, 0(t0)
                                            ; Читаем 32-битное слово в регистр a0
                                            ; Получаем сначала адрес, лежащий в input_addr
    lui         t0, %hi(input_addr)
    addi        t0, t0, %lo(input_addr)
    lw          t0, 0(t0)                   ; Теперь лежит t0 = 0x80

    lw          a0, 0(t0)                   ; Теперь входные байты лежат в a0

    jal         ra, swap_endian             ; Целевая функция
                                            ; Получаем выходной адрес в t0
    lui         t0, %hi(output_addr)
    addi        t0, t0, %lo(output_addr)
    lw          t0, 0(t0)
                                            ; Выводим на порт 0x84
    sw          a0, 0(t0)

    halt


                                            ; a0 - число
                                            ; a1 - сдвиг вправо для маски с 0xFF
                                            ; a2 - итоговый сдвиг влево
extract_and_shift:
                                            ; a0 >> a1 -> t0
    srl         t0, a0, a1
                                            ; t0 and 0xFF -> t0
    andi        t0, t0, 0xFF
                                            ; t0 << a2 -> a0
    sll         a0, t0, a2
    jr          ra


swap_endian:

    ; Выделяем кадр стека и сохраняем ra и callee-saved

    addi        sp, sp, -16 
    sw          ra, 12(sp)

    ; сохраняем callee-saved регистры s1, s2 в стек по ABI

    sw          s1, 8(sp)
    sw          s2, 4(sp) 

    ; s1 - наши байты, s2 = 0

    mv          s1, a0
    addi        s2, zero, 0

    ; Обработка нулевого байта (>> 0 + mask + << 24)

    mv          a0, s1
    addi        a1, zero, 0
    addi        a2, zero, 24
    jal         ra, extract_and_shift

    or          s2, s2, a0

    ; Обработка первого байта (>> 8 + mask + << 16)

    mv          a0, s1
    addi        a1, zero, 8
    addi        a2, zero, 16
    jal         ra, extract_and_shift

    or          s2, s2, a0

    ; Обработка второго байта (>> 16 + mask + << 8)

    mv          a0, s1
    addi        a1, zero, 16
    addi        a2, zero, 8
    jal         ra, extract_and_shift

    or          s2, s2, a0

    ; Обработка третьего байта (>> 24 + mask + << 0)

    mv          a0, s1
    addi        a1, zero, 24
    addi        a2, zero, 0
    jal         ra, extract_and_shift

    or          s2, s2, a0

    
    ; Восстанавливаем сохранённые регистры и возврат

    mv          a0, s2
    lw          s2, 4(sp)
    lw          s1, 8(sp)
    lw          ra, 12(sp)
    addi        sp, sp, 16

    jr          ra

    


