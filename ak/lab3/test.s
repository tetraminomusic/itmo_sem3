    .data
    input_addr:         .word 0x80
  

    .text
    .org 0x100

_start:

    1 a!

    0



read_loop:

    @p 0x80 b! @b

    dup

    10 xor

    if end_read



    swap

    !+

    1 +

    read_loop



end_read:

    drop

    0 b!

    dup

    !b

    dup

    if finish_pre
    halt
finish_pre:

    a!


write_loop:

    -1 a 
    + a!

    @

    @p 0x84 b! !b

    

    1 -

    dup

    if write_loop

finish:
    drop
    halt



swap:
    over >r >r drop r> r>
    ;