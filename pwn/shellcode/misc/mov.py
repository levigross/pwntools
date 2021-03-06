from pwn.internal.shellcode_helper import *
import pwn
import string

@shellcode_reqs(arch=['i386', 'amd64'])
def mov(dest, src, stack_allowed = True, recursion_depth = 1, arch = None):
    """Does a mov into the dest while newlines and null characters.

    The src can be be an immediate or another register.

    If the stack is not allowed to be used, set stack_allowed to False.
    """

    src = arg_fixup(src)
    allowed = pwn.get_only()

    if arch == 'i386':
        return _mov_i386(dest, src, stack_allowed, recursion_depth)
    elif arch == 'amd64':
        return _mov_amd64(dest, src, stack_allowed, recursion_depth)

    no_support('mov', 'any', arch)

def _fix_regs(regs, in_sizes):
    sizes = {}
    bigger = {}
    smaller = {}

    for l in regs:
        for r, s in zip(l, in_sizes):
            sizes[r] = s

        for n, r in enumerate(l):
            bigger[r] = l[:n]
            smaller[r] = l[n+1:]

    return pwn.concat(regs), sizes, bigger, smaller


def _mov_i386(dest, src, stack_allowed, recursion_depth):
    regs = [['eax', 'ax', 'al', 'ah'],
            ['ebx', 'bx', 'bl', 'bh'],
            ['ecx', 'cx', 'cl', 'ch'],
            ['edx', 'dx', 'dl', 'dh'],
            ['edi', 'di'],
            ['esi', 'si'],
            ['ebp', 'bp'],
            ['esp', 'sp'],
            ]

    all_regs, sizes, bigger, smaller = _fix_regs(regs, [32, 16, 8, 8])

    if dest not in all_regs:
        bug('%s is not a register' % str(dest))

    if isinstance(src, int):
        if src >= 2**sizes[dest] or src < -(2**(sizes[dest]-1)):
            pwn.log.warning('Number 0x%x does not fit into %s' % (src, dest))

        srcp = packs_little_endian[sizes[dest]](src)

        if src == 0:
            return 'xor %s, %s' % (bigger[dest][0], bigger[dest][0])

        if '\x00' not in srcp and '\n' not in srcp:
            return 'mov %s, 0x%x' % (dest, src)

        if stack_allowed and sizes[dest] == 32 and -128 <= src <= 127 and src != 0xa:
            return 'push 0x%x\npop %s' % (src, dest)

        if stack_allowed and sizes[dest] == 16 and -128 <= src <= 127 and src != 0xa:
            return 'push 0x%x\npop %s\ninc esp\ninc esp' % (src, dest)

        a,b = pwn.xor_pair(srcp, avoid = '\x00\n')
        u = unpacks_little_endian[sizes[dest]]
        a = u(a)
        b = u(b)
        return 'mov %s, 0x%x\nxor %s, 0x%x' % (dest, a, dest, b)

    elif src in all_regs:
        if src == dest or src in bigger[dest] or src in smaller[dest]:
            return ''
        elif sizes[dest] == sizes[src]:
            return 'mov %s, %s' % (dest, src)
        elif sizes[dest] > sizes[src]:
            return 'movzx %s, %s' % (dest, src)
        else:
            for r in bigger[dest]:
                if sizes[r] == sizes[src]:
                    return 'mov %s, %s' % (r, src)
            bug('Register %s could not be moved into %s' % (src, dest))

    bug('%s is neither a register nor an immediate' % src)

def _mov_amd64(dest, src, stack_allowed, recursion_depth):
    regs = [['rax', 'eax', 'ax', 'al'],
            ['rbx', 'ebx', 'bx', 'bl'],
            ['rcx', 'ecx', 'cx', 'cl'],
            ['rdx', 'edx', 'dx', 'dl'],
            ['rdi', 'edi', 'di', 'dil'],
            ['rsi', 'esi', 'si', 'sil'],
            ['rbp', 'ebp', 'bp', 'bpl'],
            ['rsp', 'esp', 'sp', 'spl'],
            ['r8', 'r8d', 'r8w', 'r8b'],
            ['r9', 'r9d', 'r9w', 'r9b'],
            ['r10', 'r10d', 'r10w', 'r10b'],
            ['r11', 'r11d', 'r11w', 'r11b'],
            ['r12', 'r12d', 'r12w', 'r12b'],
            ['r13', 'r13d', 'r13w', 'r13b'],
            ['r14', 'r14d', 'r14w', 'r14b'],
            ['r15', 'r15d', 'r15w', 'r15b']
            ]

    all_regs, sizes, bigger, smaller = _fix_regs(regs, [64, 32, 16, 8, 8])

    if dest not in all_regs:
        bug('%s is not a register' % str(dest))

    if isinstance(src, int):
        if src >= 2**sizes[dest] or src < -(2**(sizes[dest]-1)):
            pwn.log.warning('Number 0x%x does not fit into %s' % (src, dest))

        srcp = packs_little_endian[sizes[dest]](src)

        if src == 0:
            return 'xor %s, %s' % (bigger[dest][0], bigger[dest][0])

        if '\x00' not in srcp and '\n' not in srcp:
            return 'mov %s, 0x%x' % (dest, src)

        if stack_allowed and sizes[dest] == 64 and -128 <= src <= 127 and src != 0xa:
            return 'push 0x%x\npop %s' % (src, dest)

        # TODO: is it a good idea to transform mov('eax', 17) to mov('rax', 17)
        # automatically?
        if stack_allowed and sizes[dest] == 32 and -128 <= src <= 127 and src != 0xa:
            return 'push 0x%x\npop %s' % (src, bigger[dest][0])

        a,b = pwn.xor_pair(srcp, avoid = '\x00\n')
        u = unpacks_little_endian[sizes[dest]]
        a = u(a)
        b = u(b)
        return 'mov %s, 0x%x\nxor %s, 0x%x' % (dest, a, dest, b)

    elif src in all_regs:
        if src == dest or src in bigger[dest] or src in smaller[dest]:
            return ''
        elif sizes[dest] == sizes[src]:
            return 'mov %s, %s' % (dest, src)
        elif sizes[dest] == 64 and sizes[src] == 32:
            return 'mov %s, %s' % (smaller[dest][0], src)
        elif sizes[dest] > sizes[src]:
            return 'movzx %s, %s' % (dest, src)
        else:
            for r in bigger[dest]:
                if sizes[r] == sizes[src]:
                    return 'mov %s, %s' % (r, src)
            bug('Register %s could not be moved into %s' % (src, dest))

    bug('%s is neither a register nor an immediate' % src)
