    .data

buf:             .byte  '________________________________'
padding:         .byte  '________'

input_addr:      .word  0x80
output_addr:     .word  0x84

char_val:        .word  0
cur_ptr:         .word  0
count:           .word  0

const_0:         .word  0
const_byte_0:    .word  0x5F5F5F00
const_1:         .word  1

stop_processing: .word  0

const_FF_FF_FF_00: .word 0xFF_FF_FF_00
const00_00_00_FF: .word  0x000000FF

const_31:        .word  31                 ; Лимит слов
const_10:        .word  10                 ; код переноса строки
const_32:        .word  32                 ; смещение
const_65:        .word  65                 ; A
const_90:        .word  90                 ; Z
const_error:     .word  0xCCCCCCCC         ; Ошибка при оверфлоу


    .text

    .org         0x100

_start:
    load_imm     buf
    store        cur_ptr

    load         const_0
    store        count
    store        stop_processing

first_loop:
    
    load         input_addr
    load_acc

    ; Проверка на последний символ
    store        char_val
    sub          const_10
    beqz         second_step

    ; Проверка на переполнение
    load         count
    sub          const_31
    bgez         overflow_error

    load         char_val
    store_ind    cur_ptr

    load         cur_ptr
    add          const_1
    store        cur_ptr

    load         count
    add          const_1
    store        count

    jmp          first_loop
    

; Проход по буферу + ловеркейс его и параллельно вывод.

second_step:

    load         const_byte_0
    store_ind    cur_ptr
    
    load_imm     buf
    store        cur_ptr

second_loop:

    ; Делаем второй проход, читаем посимвольно
    
    load         cur_ptr
    load_acc

    and const00_00_00_FF

    ; тут уже lowercase пошёл

    store       char_val    
    sub         const_10
    beqz        programm_end

    load         char_val
    sub          const_65
    bltz         store_char

    load         char_val
    sub          const_90
    bgtz         store_char

    load         char_val
    add          const_32
    store        char_val

; Закидываем символ в массив

store_char:

    ; Проверяем на конечный символ

    load        char_val
    beqz        programm_end

    store_ind   output_addr

    ; Читаем 32 байта из буфера
    
    load cur_ptr
    load_acc

    ; Срезаем байт, который хотим записать

    and const_FF_FF_FF_00
    add char_val

    ; Кладём обработанный вариант

    store_ind cur_ptr

    load        cur_ptr
    add         const_1
    store       cur_ptr

    jmp         second_loop   

overflow_error:
    load         const_error
    store_ind    output_addr

programm_end:
    halt

