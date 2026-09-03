        .data

input_addr:         .word 0x80
output_addr:        .word 0x84        

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
    0 swap                      \ 0 - это количество десятков (q), а r - остаток
divmod_loop:
    dup -10 +                   \ Вычитаем десяточку
    -if divmod_sub              \ Если ещё есть 10, то идём вычитать
    ;
divmod_sub:
    -10 +
    swap 1 + swap
    divmod_loop ;

                                \ Основной цикл наращивания суммы

sum_digits:
    abs_maker
    0 swap

sum_while:
    dup
    if sum_finish               \ Проверяем, что число это 0

    divmod_10                   \ (sum q r)
    >r                          \ (sum q) (r)
    swap                        \ (q sum) (r)
    r>                          \ (q sum r)
    +                           \ (q new_sum)
    swap                        \

    sum_while ;

sum_finish:
    drop
    ;
