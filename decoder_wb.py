'''
Программа запускается с изображением, имя (или расположение) которого передается параметром в консоли,
если нчиего не указано, то программа будет запущена на изображении с именем "pic.jpg"
Работает с чёрно-белыми одноканальными изображениями с длиной значений 1.
На выходе создаёт 1 файл "pic.pgm" - декодированное пиксельное изображение.
'''


import math
import re
import time
from sys import argv

prec, height, width, channels = 0, 0, 0, 0          # Параметры изображения из маркера SOF0, prec - разрядность каналов
y_id, h_1, v_1, quant_t1 = 0, 0, 0, 0               # id канала нужно при квантовании
t_amnt = 0
r_height, r_width = 0, 0
tables, dc_c, ac_c = {}, [], []                      # tables - таблицы квантования
y_ch = []
zigzag = [[1,  2,   6,  7, 15, 16, 28, 29],
          [3,  5,   8, 14, 17, 27, 30, 43],
          [4,  9,  13, 18, 26, 31, 42, 44],
          [10, 12, 19, 25, 32, 41, 45, 54],
          [11, 20, 24, 33, 40, 46, 53, 55],
          [21, 23, 34, 39, 47, 52, 56, 61],
          [22, 35, 38, 48, 51, 57, 60, 62],
          [36, 37, 49, 50, 58, 59, 63, 64]]

zzt = [[ 0,  1,  8, 16,  9,  2,  3, 10],
       [17, 24, 32, 25, 18, 11,  4,  5],
       [12, 19, 26, 33, 40, 48, 41, 34],
       [27, 20, 13,  6,  7, 14, 21, 28],
       [35, 42, 49, 56, 57, 50, 43, 36],
       [29, 22, 15, 23, 30, 37, 44, 51],
       [58, 59, 52, 45, 38, 31, 39, 46],
       [53, 60, 61, 54, 47, 55, 62, 63]]


def frmt(n, bits):
    mask = (1 << bits) - 1
    if n < 0:
        n = ((abs(n) ^ mask) + 1)
        binary_str = (bin(n & mask))[2:]
        coef = binary_str[8:] + binary_str[:8]
        return coef
    elif n == 0:
        return '0'*bits
    else:
        binary_str = bin(n)[2:].zfill(16)
        coef = binary_str[8:] + binary_str[:8]
        return coef


def new_table(t_id):
    if t_id in tables.keys():
        print('Ошибка при создании таблицы DQT, таблица с данным id уже существует.')
    else:
        tables[t_id] = [['00' for _ in range(8)] for _ in range(8)]


def img2hex(name):
    # Перевод картинки в формат строки с удобным для дальнейшей работы форматированием
    string = ''
    with open(name, 'rb') as f:
        bin_value = f.read(1)
        while len(bin_value) != 0:
            hex_val = hex(ord(bin_value))[2:] + ' '     # Пишем без 0x, а в конец добавляем пробел
            if len(hex_val) == 2:
                hex_val = '0' + hex_val
            string += hex_val
            bin_value = f.read(1)
    return string[0:-1:1]   # возвращаем строку без пробела в конце


def cut(bpic):
    # Т.к. для JFIF изображений сегмент FF e_ обязательно следует за d8, выполняется проверка на наличие этого сегмента,
    # считывается его длина, затем он удаляется полностью из последовательности. После этого выполняется проверка на
    # наличие сегмента с комментарием, который тоже вырезается в случае наличия, возврщается последовательность начиная
    # с сегмента ff db (таблица квантования).
    if bpic[0:4] != 'ff e':
        print("Не JFIF.")
    else:
        # print('JFIF!')
        len = int(bpic[6], 16)*4096 + int(bpic[7], 16)*256 + int(bpic[9], 16)*16 + int(bpic[10], 16) + 2
        bpic = bpic[len*3:]
    if bpic[0:5] != 'ff fe':
        # print("Комментарий отсутствует")
        pass
    else:
        # print("Комментарий удалён")
        len = int(bpic[9], 16)*16 + int(bpic[10], 16) + 2
        bpic = bpic[len*3:]
    if bpic[0:5] == 'ff c2':
        print("Маркер ff c2. Не поддерживается.")
        exit(1)
    return bpic


def dqt(bpic):
    # На вход подаётся строка, начинающаяся сразу после "ff db",
    lenn = int(bpic[0], 16)*4096 + int(bpic[1], 16)*256 + int(bpic[3], 16)*16 + int(bpic[4], 16)
    if bpic[6] == '0':
        # data_len = 1
        pass
    elif bpic[6] == '1':
        # data_len = 2
        print("Неподдерживаемая длина значений в таблице (длина 2). Выход.")
        exit(1)
    else:
        print("Ошибка на этапе DQT!\nВыход.")
        exit(1)
    table_id = bpic[7]
    new_table(table_id)
    for i in range(8):
        for j in range(8):
            tables[table_id][i][j] = bpic[(zigzag[i][j]+2)*3] + bpic[(zigzag[i][j]+2)*3+1]
    return bpic[lenn*3:]


def sof0(bpic):
    # Header, ff c0
    len = int(bpic[0], 16) * 4096 + int(bpic[1], 16) * 256 + int(bpic[3], 16) * 16 + int(bpic[4], 16)
    global prec, height, width, channels, y_id, h_1, v_1  # , cb_id, cr_id, h_2, h_3, v_2, v_3, y_ts, cb_ts, cr_ts
    prec = int(bpic[6], 16) * 16 + int(bpic[7], 16)
    global r_height, r_width
    r_height = int(bpic[9], 16) * 4096 + int(bpic[10], 16) * 256 + int(bpic[12], 16) * 16 + int(bpic[13], 16)
    r_width = int(bpic[15], 16) * 4096 + int(bpic[16], 16) * 256 + int(bpic[18], 16) * 16 + int(bpic[19], 16)
    height, width = math.ceil(r_height / 8) * 8, math.ceil(r_width / 8) * 8
    channels = int(bpic[21], 16) * 16 + int(bpic[22], 16)
    global quant_t1
    y_id, h_1, v_1, quant_t1 = int(bpic[24:26], 16), int(bpic[27], 16), int(bpic[28], 16), int(bpic[30:32], 16)
    return bpic[len*3:]


def huffmantable(bpic):
    lenn = int(bpic[0], 16) * 4096 + int(bpic[1], 16) * 256 + int(bpic[3], 16) * 16 + int(bpic[4], 16)
    dct = dc_c if bpic[6] == '0' else ac_c
    tid = int(bpic[7])
    lst, ptr = [0 for _ in range(16)], 9
    for i in range(16):
        lst[i] = int(bpic[ptr], 16)*16 + int(bpic[ptr+1], 16)
        ptr += 3
    dct.append({})
    cnt = '0'
    for i in range(16):
        for j in range(lst[i]):
            dct[tid][bin(int(cnt, 2))[2:].zfill(len(cnt))] = bpic[ptr]+bpic[ptr+1]
            ptr += 3
            cnt = bin(int(cnt, 2) + 1)[2:].zfill(len(cnt))
        cnt += '0'
    return bpic[lenn*3:]


def scanner(bitline, y_id_dc, y_id_ac):
    print("Секция FF DA. Сканирование...")
    global t_amnt
    t_amnt = height * width // 64
    ptr, tid_dc, tid_ac = 0, y_id_dc, y_id_ac                                   # Указатель на позицию бита в строке
    arr = [[[0 for _ in range(8)] for _ in range(8)] for _ in range(t_amnt)]    # Делаем таблицы нулей
    out = [[] for _ in range(t_amnt)]
    for k in range(t_amnt):
        plc = 0                                     # Указатель на место в заполняемой таблице
        for i in range(16):                         # Заполнение DC - коэффициентов
            ln_dc = bitline[ptr:ptr+i+1]            # Подбирается код, который можно декодировать, берётся его значение
            if ln_dc in dc_c[tid_dc].keys():
                ptr += (i + 1)
                num = int(dc_c[tid_dc][ln_dc], 16)
                x, y = zzt[plc // 8][plc % 8] // 8, zzt[plc // 8][plc % 8] % 8
                prev = arr[k - 1][x][y] if k != 0 else 0
                if num == 0:
                    arr[k][x][y] = prev
                    out[k].append(prev)
                else:
                    var = bitline[ptr:ptr+num]
                    ptr = ptr + num
                    if var[0] == '1':
                        arr[k][x][y] = int(var, 2) + prev  # Кладём в табл.
                        out[k].append(int(var, 2) + prev)
                    elif var[0] == '0':
                        kek = int(var, 2) - (2 ** num) + 1
                        arr[k][x][y] = kek + prev
                        out[k].append(kek + prev)
                    else:
                        print("Неправильная последовательность битов.")
                        exit(1)
                plc += 1
                break
            elif i == 15:
                exit(1)
        while plc <= 63:                             # AC - коэффициенты
            for i in range(16):
                ln_ac = bitline[ptr:ptr+i+1]
                if ln_ac in ac_c[tid_ac].keys():
                    ptr += (i + 1)
                    if int(ac_c[tid_ac][ln_ac], 16) == 0:
                        for _ in range(64-plc):
                            out[k].append(0)
                        plc = 64
                    else:
                        tmp = int(ac_c[tid_ac][ln_ac][0], 16)
                        plc += tmp
                        for _ in range(tmp):
                            out[k].append(0)
                        num_ac = int(int(ac_c[tid_ac][ln_ac][1], 16))
                        var_ac = bitline[ptr:ptr + num_ac]
                        ptr += num_ac
                        x, y = zzt[plc // 8][plc % 8] // 8, zzt[plc // 8][plc % 8] % 8
                        if len(var_ac) > 0:
                            if var_ac[0] == '1':
                                arr[k][x][y] = int(var_ac, 2)
                                out[k].append(int(var_ac, 2))
                            elif var_ac[0] == '0':
                                kek = int(var_ac, 2) - (2 ** num_ac) + 1
                                arr[k][x][y] = kek
                                out[k].append(kek)
                            else:
                                print("Неправильная последовательность битов.")
                                exit(1)
                        plc += 1
                    break
                else:
                    if i == 15:
                        exit(1)
    return arr


def sos(bpic):
    # Start of Scan, ff da
    size = int(bpic[0], 16) * 4096 + int(bpic[1], 16) * 256 + int(bpic[3], 16) * 16 + int(bpic[4], 16)
    components = int(bpic[6], 16) * 16 + int(bpic[7], 16)
    if components == 3:
        exit("Количество компонент 3! Выход")
    if components == 1:
        c_one, c_one_dc, c_one_ac = int(bpic[9], 16) * 16 + int(bpic[10], 16), int(bpic[12], 16), int(bpic[13], 16)
        bpic = bpic[size*3:]
        bpic = re.sub('ff 00', 'ff', bpic)
        bits = ''
        for i in range(len(bpic)//3 + 1):
            bits += bin(int(bpic[i*3:i*3+2], 16))[2:].zfill(8)
        return scanner(bits, c_one_dc, c_one_ac)


def dkp(matrix):
    memtrix = [[0 for _ in range(8)] for _ in range(8)]
    val = 0.0
    for y in range(8):                      # x и у - для конкретного эл-та матрицы
        for x in range(8):
            for v in range(8):              # u - столбец, v - строка
                if v == 0:
                    cv = 1 / math.sqrt(2)
                else:
                    cv = 1.0
                for u in range(8):          # u и v становятся равны 1, когда итерация > 0
                    if u == 0:
                        cu = 1 / math.sqrt(2)
                    else:
                        cu = 1.0
                    val += float(cu) * float(cv) * matrix[v][u] * (math.cos((((2 * x) + 1) * u * math.pi) / 16)) * (math.cos((((2 * y) + 1) * v * math.pi) / 16))
            memtrix[y][x] = int(val / 4)
            val = 0.0
    return memtrix


def computation(matrices):
    global y_ch
    print("Этап вычислений...")
    for i in range(t_amnt):
        for x in range(8):
            for y in range(8):
                matrices[i][x][y] *= int(tables[str(quant_t1)][x][y], 16)
        y_ch.append(dkp(matrices[i]))


def converter():        # Записывает все таблицы в одну большую
    wb_pic = [[0 for _ in range(width)] for _ in range(height)]
    t_id = 0
    for v in range(height // 8):
        for h in range(width // 8):
            for i in range(8):
                for j in range(8):
                    y_v = y_ch[t_id][i][j]
                    pix = 128 + int(y_v) if int(y_v) >= -128 else 0
                    wb_pic[v * 8 + i][h * 8 + j] = pix if pix < 256 else 255
            t_id += 1
    return wb_pic


def writer(f_name, bp):
    with open(f_name, 'w') as fp:
        fp.write('P2\n' + str(r_width) + ' ' + str(r_height) + '\n255\n')
        for i in range(r_height):
            for j in range(r_width):
                fp.write(str(bp[i][j]) + ' ')
            fp.write('\n')
    print('Изображение записано в файл.')


def decoder(name):
    bytepic = img2hex(name)
    if bytepic[0:5] != 'ff d8' or bytepic[-5:] != 'ff d9':    # Проверка, что начало и конец соответствуют Jpeg`у
        print('Ошибка, файл не является JPEG!')
        exit(1)
    bytepic = cut(bytepic[6:])
    while bytepic[0:5] != 'ff da':          # Пока не SOS
        if bytepic[0:5] == 'ff db':         # Построение таблиц квантования
            bytepic = dqt(bytepic[6:])
        elif bytepic[0:5] == 'ff c0':       # Считывание информации об изображении
            bytepic = sof0(bytepic[6:])
        elif bytepic[0:5] == 'ff c4':       # Построение кодов Хаффмана (не деревом, а словарём)
            bytepic = huffmantable(bytepic[6:])
        elif bytepic[0:5] == 'ff c2' or 'ff e':  # Вырезание маркера ff c2
            bytepic = cut(bytepic)
    print('Словари кодов Хаффмана записаны.')
    matrices = sos(bytepic[6:])
    computation(matrices)
    wb = converter()
    writer('result.pgm', wb)


params = argv[1:]
filename = params[0] if len(params) else 'pic.jpg'
print('Чтение изображения', filename)
start_time = time.time()
decoder(filename)
print('Время выполнения программы:', round(time.time()-start_time, 3), "секунд.")
