.data

input_addr:     .word 0x80
output_addr:    .word 0x84

const_0:        .word 0
const_1:        .word 1
const_3:        .word 3
const_4:        .word 4

n:              .word 0
cur_ptr:        .word 0

buffer:         .word 0, 0, 0, 0

    .text
_start:
    load           input_addr
    load_acc        
    store           n

    load_imm       buffer
    store          cur_ptr

if:
    load           n
    beqz           end_loop

    load           const_3
    store_ind      cur_ptr

    load           cur_ptr
    add            const_1         ; <-- Шаг на следующее 32-битное слово (+4 байта)
    store          cur_ptr

    load           n
    sub            const_1         ; <-- Счетчик уменьшаем на 1
    store          n

    jmp            if

end_loop:
    load           const_0
    store_ind      output_addr
    halt