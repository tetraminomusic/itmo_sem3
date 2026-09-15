    .data

input_addr:      .word  0x80
output_addr:     .word  0x84

const_10:        .word  10

    .text
    .org 0x100

_start:
    \ @p input_addr - выталиквает значение из определённого адреса в стек данных
    \ a! - сохранить верхнее значение стека данных в регистре а
    \ @ - выталиквает значение из адреса в регистре А в стек данных
    @p input_addr a! @
    sum_digits

    \ @p output_addr - достаём выходной адрес, помещая его в стек
    \ a! - сохраняем верхнее значение стека данных в регистр А
    \ ! - по адресу в регистре А сохраняем верхнее значение стека
    @p output_addr a! !
    halt

    \ Получение модуля числа
abs_maker:
    dup
    -if abs_done
    inv 1 +
abs_done:
    ;

    \ Обмен между двумя верхними значениями, лежащими на стеке

swap:
    over >r >r drop r> r>
    ;

    \ Деление с остатком на 10
divmod_10:
    a!
    lit const_10 b!

    0
    0

    31 >r

div_loop:
    +/
    next div_loop

    swap
    ;

    \ Основной цикл наращивания суммы

sum_digits:
    abs_maker
    0 swap

sum_while:
    dup
    if sum_finish            \ Проверяем, что число это 0

    divmod_10                \ (sum q r)
    >r                       \ (sum q) (r)
    swap                     \ (q sum) (r)
    r>                       \ (q sum r)
    +                        \ (q new_sum)
    swap                     \

    sum_while ;

sum_finish:
    drop
    ;

