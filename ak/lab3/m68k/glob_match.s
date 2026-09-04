            .data

    input_addr:  .word 0x80
    output_addr: .word 0x84

    stack_top:   .word 0x1000

    pattern_buf: .byte 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0
    text_buf:    .byte 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0

            .text
            .org 0x100
                                ; A0 - адрес начала буфера
                                ; D0 = 0 - успех, D0 = -1 - переполнение
                                ; D1 - счётчик длины
                                ; D2 - текущий прочитанный символ

read_line:
    move.l  0, D1

    movea.l input_addr, A2
    movea.l (A2), A2             ; 0x80 -> A2

read_loop:
    move.l  (A2), D2

    cmp.l   10, D2              ; ?= \n
    beq     read_finish

    cmp.l   31, D1              ; проверяем, переполнен ли буфер
    bge     read_overflow

    move.b  D2, (A0)+           ; Далее идёт запись символа в буфер
    add.l   1, D1               ; Увеличиваем счётчик D1

    jmp     read_loop
read_finish:
    ; записывает нул терминатор
    move.b  0, (A0)
    move.l  0, D0
    rts

read_overflow:
    move.l -1, D0
    rts


match_recursive:
    move.l  D4, -(A7)           ; Указатель на текущий символ в pattern
    move.l  D5, -(A7)           ; Указатель на текущий символ в text
    move.l  D2, -(A7)           ; Текущий символ в pattern
    move.l  D3, -(A7)           ; Текущий символ в text

    move.b  0(A0, D4), D2       ; D2 = pattern[D4]
    move.b  0(A1, D5), D3       ; D3 = text[D5]

    cmp.b   0, D2
    bne     check_wildcard_star ; Проверяем, мало ли паттерн закончился

    cmp.b   0, D3
    beq     ret_true
    jmp     ret_false

check_wildcard_star:
    cmp.b   '*', D2
    bne     check_normal_chars   ; Проверка обычных символов

    ; Если * - пустая строка

    add.l   1, D4
    jsr     match_recursive
    cmp.l   1, D0
    beq     match_epilogue

    ; Делаем откат

    sub.l   1, D4
    cmp.b   0, D3               ; Проверяем, закончился ли текст
    beq     ret_false

    ; Если текст не пуст, то сдвигаем D5 на 1 символ вперёд

    add.l   1, D5
    jsr     match_recursive
    jmp     match_epilogue

check_normal_chars:
    cmp.b   0, D3               ; Если текст закончился, а в шаблоне осталась буква
    beq     ret_false
                                ; Если в шаблоге знак '?'
    cmp.b   '?', D2
    beq     match_step
                                ;  Точно совпадение
    cmp.b   D2, D3
    beq     match_step
    jmp     ret_false

match_step:
    add.l   1, D4
    add.l   1, D5
    jsr     match_recursive
    jmp     match_epilogue

ret_true:
    move.l  1, D0
    jmp     match_epilogue

ret_false:
    move.l  0, D0
    jmp     match_epilogue

match_epilogue:
    move.l (A7)+, D3
    move.l (A7)+, D2
    move.l (A7)+, D5
    move.l (A7)+, D4
    rts


_start:

    ; Инициализация стека
    movea.l stack_top, A7
    movea.l (A7), A7

    ; Читаем строку pattern в pattern_buf
    ; Инициализируем A0 как адрес начала массива, куда мы будем писать данные
    ; Чекаем D0, если 0 - огонь, если -1 - беда

    movea.l pattern_buf, A0
    jsr     read_line
    cmp.l   0, D0
    blt     trigger_overflow

    ; Повторяем операцию, но уже для text в text_buf
    movea.l text_buf, A0
    jsr     read_line
    cmp.l   0, D0
    blt     trigger_overflow

    ; Сопоставление паттерна и текста

    move.l  0, D4
    move.l  0, D5

    movea.l pattern_buf, A0
    movea.l text_buf, A1
    jsr     match_recursive

    movea.l output_addr, A3
    movea.l (A3), A3
    move.l  D0, (A3)
    halt

trigger_overflow:
    movea.l output_addr, A3
    movea.l (A3), A3
    move.l  0xCCCC_CCCC, D0
    move.l  D0, (A3)
    halt  