section .text

global exit
global string_length
global print_string
global print_char
global print_newline
global print_uint
global print_int
global string_equals
global read_char
global read_word
global parse_uint
global parse_int
global string_copy

; Принимает код возврата в rdi и завершает текущий процесс

exit: 
    mov rax, 60
    syscall

; Принимает указатель на нуль-терминированную строку (rdi), возвращает её длину в rax

string_length:
    xor rax, rax

.loop:
    cmp byte [rdi + rax], 0
    je .end
    inc rax
    jmp .loop
.end:
    ret

; Принимает указатель на нуль-терминированную строку (rdi), выводит её в stdout

print_string:
    push rdi                    ; Сохраняем, так ка string_length затрёт rdi
    call string_length
    pop rsi                     

    mov rdx, rax                ; длина строки
    mov rdi, 1                  ; stdout
    mov rax, 1                  ; sys_write

    syscall
    ret

; Принимает код символа в rdi и выводит его в stdout

print_char:
    push rdi                
    mov rsi, rsp            
    mov rdx, 1              ; длина
    mov rdi, 1              ; stdout
    mov rax, 1              ; sys_write

    syscall
    pop rdi
    ret

; Переводит строку (выводит символ с кодом 0xA)

print_newline:
    mov rdi, 0xA
    jmp print_char
    
; Выводит беззнаковое 8-байтовое число (rdi) в десятичном формате

print_uint:

    ; Результат будет накапливаться в rax

    mov rax, rdi
    mov r8, 10
    sub rsp, 24             
    mov byte [rsp + 23], 0  ; нуль-терминатор в конце буфера, дабы удобно было выводить
    lea rsi, [rsp + 23]

.loop:
    dec rsi
    xor rdx, rdx
    div r8

    ; Частое лежит в rax, остаток в dl

    add dl, '0'

    mov [rsi], dl
    test rax, rax
    jnz .loop

    mov rdi, rsi
    call print_string

    add rsp, 24
    ret

; Выводит знаковое 8-байтовое число (rdi) в десятичном формате

print_int:
    cmp rdi, 0
    jns .positive

    push rdi                
    mov rdi, '-'
    call print_char
    pop rdi
    neg rdi

.positive:
    jmp print_uint

; Принимает два указателя на строки (rdi, rsi), возвращает 1 если они равны, 0 иначе

string_equals:
.loop:
    mov al, byte [rdi]
    mov dl, byte [rsi]

    cmp al, dl
    jne .not_equal

    test al, al
    jz .equal

    inc rdi
    inc rsi
    jmp .loop

.not_equal:
    xor rax, rax
    ret

.equal:
    mov rax, 1
    ret

; Читает один символ из stdin в rax. Возвращает 0 если достигнут конец потока (EOF)

read_char:
    sub rsp, 8              
    mov rax, 0              ; sys_read
    mov rdi, 0              ; stdin
    mov rsi, rsp            ; буфер на стеке
    mov rdx, 1              ; 1 байт
    syscall

    ; проверяем, что не eof

    test rax, rax
    jle .eof

    movzx rax, byte [rsp]
    add rsp, 8
    ret

.eof:
    xor rax, rax
    add rsp, 8
    ret

; Принимает: адрес начала буфера (rdi), размер буфера (rsi)
; Возвращает в rax адрес буфера, в rdx длину слова. 0 в rax при ошибке.

read_word:
    push r12
    push r13
    push r14                

    mov r12, rdi            ; адрес буфера
    mov r13, rsi            ; размер буфера
    xor r14, r14            ; счётчик длины слова

.skip_spaces:
    call read_char
    test rax, rax
    jz .fail

    ; Пропуск пробельных символов

    cmp al, 0x20
    je .skip_spaces
    cmp al, 0x9
    je .skip_spaces
    cmp al, 0xA
    je .skip_spaces

    ; Буфер должен вместить символ и нуль-терминатор

    cmp r13, 1
    jbe .fail

    mov byte [r12 + r14], al
    inc r14

.read_loop:
    call read_char
    test rax, rax
    jz .success_end

    cmp al, 0x20
    je .success_end
    cmp al, 0x9
    je .success_end
    cmp al, 0xA
    je .success_end

    mov rcx, r13
    dec rcx
    cmp r14, rcx
    jae .fail

    mov byte [r12 + r14], al
    inc r14
    jmp .read_loop

.success_end:
    mov byte [r12 + r14], 0
    mov rax, r12
    mov rdx, r14
    jmp .end

.fail:
    xor rax, rax
    xor rdx, rdx

.end:
    pop r14
    pop r13
    pop r12
    ret

; Принимает указатель на строку (rdi), читает беззнаковое число
; Возвращает в rax: число, rdx: длину в символах (0 если прочитать не удалось)

parse_uint:
    xor rax, rax
    xor r8, r8

.loop:
    movzx r9, byte [rdi + r8]

    cmp r9, '0'
    jb .end
    cmp r9, '9'
    ja .end

    sub r9, '0'

    mov rcx, 10
    mul rcx                 ; rax = rax * 10 (rdx затирается)

    add rax, r9
    inc r8
    jmp .loop

.end:
    mov rdx, r8
    ret

; Принимает указатель на строку (rdi), читает знаковое число
; Возвращает в rax: число, rdx: длину в символах с учётом знака

parse_int:
    mov al, byte [rdi]

    cmp al, '-'
    je .is_negative

    cmp al, '+'
    je .is_positive

    jmp parse_uint

.is_negative:
    inc rdi
    push rdi                
    call parse_uint
    pop rdi

    test rdx, rdx
    jz .fail

    neg rax
    inc rdx                 ; учитываем знак '-' в длине
    ret

.is_positive:
    inc rdi
    push rdi                ; 8 - 8 = 0 mod 16
    call parse_uint
    pop rdi

    test rdx, rdx
    jz .fail

    inc rdx                 ; учитываем знак '+' в длине
    ret

.fail:
    xor rax, rax
    xor rdx, rdx
    ret

; Принимает: указатель на строку (rdi), буфер (rsi), размер буфера (rdx)
; Возвращает длину строки, если она поместилась (с нуль-терминатором), иначе 0

string_copy:
    push rdi
    push rsi
    push rdx                ; 3 push = 24 байта -> (8 - 24) = 0 mod 16

    call string_length

    pop rdx
    pop rsi
    pop rdi

    inc rax                 ; учитываем нуль-терминатор
    cmp rax, rdx
    ja .too_long
    dec rax

    xor rcx, rcx

.copy_loop:
    mov dl, byte [rdi + rcx]
    mov byte [rsi + rcx], dl
    test dl, dl
    jz .success
    inc rcx
    jmp .copy_loop

.success:
    mov rax, rcx
    ret

.too_long:
    xor rax, rax
    ret
