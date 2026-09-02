    .data

;buf:            .byte '_', '_', '_', '_', '_', '_', '_', '_'
;                .byte '_', '_', '_', '_', '_', '_', '_', '_'
;                .byte '_', '_', '_', '_', '_', '_', '_', '_'
;                .byte '_', '_', '_', '_', '_', '_', '_', '_'

buf:            .byte  '________________________________'
padding:        .byte  '________'

input_addr:     .word 0x80
output_addr:    .word 0x84

char_val:       .word 0
cur_ptr:        .word 0
count:          .word 0

const_0:        .word 0
const_1:        .word 1

const_31:       .word 31 ; Лимит слов
const_10:       .word 10 ; код переноса строки
const_32:       .word 32 ; смещение
const_65:       .word 65 ; A
const_90:       .word 90 ; Z
const_error:    .word 0xCCCC_CCCC


    .text

.org 0x100

_start:
    load_imm    buf
    store       cur_ptr

    load        const_0
    store       count

read_loop:
    load        input_addr
    load_acc
    store       char_val
    sub         const_10
    ; Проверка на последний символ
    beqz        finish_string

    ; Пришел EOF без переноса
    load        char_val
    beqz        overflow_error

    ; Проверка на переполнение
    load        count
    sub         const_31
    bgez        overflow_error

    ;Тут идёт уже проверка на заглавную букву в плане диапазона от 65 до 90

    load        char_val
    sub         const_65
    bltz        store_char

    load        char_val
    sub         const_90
    bgtz        store_char

    load        char_val
    add         const_32
    store       char_val

; Закидываем символ в массив
store_char:
    load        char_val
    store_ind   cur_ptr
    load        cur_ptr
    add         const_1
    store       cur_ptr
    load        count
    add         const_1
    store       count
    jmp read_loop   

; Проблема с оверфлоу
overflow_error:
    load        const_error
    store_ind   output_addr
    halt

; Если длина закончилась
finish_string:
    load        const_0
    store_ind   cur_ptr
    load        const_0
    store_ind   output_addr
    halt

    