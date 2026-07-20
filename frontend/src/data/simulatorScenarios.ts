export type BlockStatus = "valid" | "freed" | "overflowed" | "leaked" | "dangling" | "corrupted" | "written" | "null";

export interface MemBlock { id: string; label: string; status: BlockStatus; region: "stack" | "heap"; }
export interface SimFrame { caption: string; code?: string; blocks: MemBlock[]; }
export interface SimScenario { id: string; title: string; summary: string; cwe: string; frames: SimFrame[]; }

export const SCENARIOS: SimScenario[] = [
  {
    id: "buffer-overflow",
    title: "Buffer Overflow",
    summary: "Writing past the end of a fixed-size stack buffer overwrites adjacent memory.",
    cwe: "CWE-120",
    frames: [
      { caption: "A 8-byte buffer is declared on the stack, next to a saved return address.", code: "char buf[8];", blocks: [
        { id: "buf", label: "buf[8]", status: "valid", region: "stack" },
        { id: "ret", label: "return addr", status: "valid", region: "stack" },
      ] },
      { caption: "strcpy() copies 20 bytes of attacker input into the 8-byte buffer.", code: "strcpy(buf, attacker_input); // 20 bytes", blocks: [
        { id: "buf", label: "buf[8]", status: "written", region: "stack" },
        { id: "ret", label: "return addr", status: "valid", region: "stack" },
      ] },
      { caption: "The overflow spills past the buffer and overwrites the saved return address.", blocks: [
        { id: "buf", label: "buf[8]", status: "overflowed", region: "stack" },
        { id: "ret", label: "return addr", status: "corrupted", region: "stack" },
      ] },
      { caption: "When the function returns, execution jumps to the attacker-controlled address.", blocks: [
        { id: "buf", label: "buf[8]", status: "overflowed", region: "stack" },
        { id: "ret", label: "return addr → ??? ", status: "corrupted", region: "stack" },
      ] },
    ],
  },
  {
    id: "use-after-free",
    title: "Use After Free",
    summary: "A pointer is dereferenced after its memory has already been released back to the allocator.",
    cwe: "CWE-416",
    frames: [
      { caption: "A heap object is allocated and a pointer references it.", code: "Obj *p = malloc(sizeof(Obj));", blocks: [{ id: "obj", label: "Obj @0x4000", status: "valid", region: "heap" }] },
      { caption: "The object is freed -- the memory is returned to the allocator.", code: "free(p);", blocks: [{ id: "obj", label: "Obj @0x4000", status: "freed", region: "heap" }] },
      { caption: "The pointer 'p' still holds the old address -- it is now dangling.", code: "// p still points to 0x4000", blocks: [{ id: "obj", label: "freed block", status: "dangling", region: "heap" }] },
      { caption: "The code dereferences 'p' -- reading or writing memory that may now belong to something else.", code: "p->value = 42; // USE AFTER FREE", blocks: [{ id: "obj", label: "freed block", status: "corrupted", region: "heap" }] },
    ],
  },
  {
    id: "double-free",
    title: "Double Free",
    summary: "free() is called twice on the same pointer, corrupting the heap allocator's internal state.",
    cwe: "CWE-416",
    frames: [
      { caption: "A heap object is allocated.", code: "char *p = malloc(64);", blocks: [{ id: "obj", label: "block @0x5000", status: "valid", region: "heap" }] },
      { caption: "The object is freed once -- normal.", code: "free(p);", blocks: [{ id: "obj", label: "block @0x5000", status: "freed", region: "heap" }] },
      { caption: "free() is called AGAIN on the same pointer.", code: "free(p); // double free!", blocks: [{ id: "obj", label: "block @0x5000", status: "corrupted", region: "heap" }] },
      { caption: "The allocator's free-list is now corrupted -- future malloc() calls can return overlapping or attacker-influenced addresses.", blocks: [{ id: "obj", label: "allocator state corrupted", status: "corrupted", region: "heap" }] },
    ],
  },
  {
    id: "null-deref",
    title: "NULL Pointer Dereference",
    summary: "A pointer that may be NULL is dereferenced without a prior check.",
    cwe: "CWE-476",
    frames: [
      { caption: "malloc() is called, but the system is out of memory.", code: "char *buf = malloc(huge_size);", blocks: [{ id: "buf", label: "buf = NULL", status: "null", region: "heap" }] },
      { caption: "No check is performed before use.", code: "// no if (buf == NULL) check", blocks: [{ id: "buf", label: "buf = NULL", status: "null", region: "heap" }] },
      { caption: "The code dereferences the NULL pointer -- the process crashes immediately.", code: "buf[0] = 'x'; // CRASH", blocks: [{ id: "buf", label: "SIGSEGV", status: "corrupted", region: "heap" }] },
    ],
  },
  {
    id: "memory-leak",
    title: "Memory Leak",
    summary: "Allocated memory is never freed, and the pointer to it goes out of scope.",
    cwe: "CWE-401",
    frames: [
      { caption: "A heap block is allocated inside a function.", code: "void f() {\n  char *buf = malloc(1024);", blocks: [{ id: "obj", label: "block @0x6000", status: "valid", region: "heap" }] },
      { caption: "An early-return path is taken, skipping the free() at the end.", code: "  if (error) return; // leak!", blocks: [{ id: "obj", label: "block @0x6000", status: "leaked", region: "heap" }] },
      { caption: "The function returns -- 'buf' (the only reference) goes out of scope.", code: "}", blocks: [{ id: "obj", label: "unreachable, still allocated", status: "leaked", region: "heap" }] },
      { caption: "Repeated calls accumulate leaked blocks until the process runs out of memory.", blocks: [
        { id: "obj1", label: "leaked #1", status: "leaked", region: "heap" },
        { id: "obj2", label: "leaked #2", status: "leaked", region: "heap" },
        { id: "obj3", label: "leaked #3", status: "leaked", region: "heap" },
      ] },
    ],
  },
  {
    id: "dangling-pointer",
    title: "Dangling Pointer",
    summary: "A pointer outlives the stack frame of the local variable it referenced.",
    cwe: "CWE-562",
    frames: [
      { caption: "A function returns the address of a local (stack) variable.", code: "int *get_value() {\n  int local = 42;\n  return &local;", blocks: [{ id: "local", label: "local = 42", status: "valid", region: "stack" }] },
      { caption: "The function returns -- its stack frame is popped and considered invalid.", code: "}", blocks: [{ id: "local", label: "popped frame", status: "freed", region: "stack" }] },
      { caption: "The caller's pointer now references memory that the next function call will overwrite.", code: "int *p = get_value();", blocks: [{ id: "local", label: "dangling", status: "dangling", region: "stack" }] },
      { caption: "The next function call reuses that stack space -- reading through 'p' yields garbage.", code: "other_function();\nprintf(\"%d\", *p); // garbage", blocks: [{ id: "local", label: "overwritten by other_function()", status: "corrupted", region: "stack" }] },
    ],
  },
  {
    id: "heap-corruption",
    title: "Heap Corruption",
    summary: "Writing past the end of a heap allocation corrupts the allocator's bookkeeping for the NEXT block.",
    cwe: "CWE-787",
    frames: [
      { caption: "Two adjacent heap blocks are allocated back to back.", code: "char *a = malloc(16);\nchar *b = malloc(16);", blocks: [
        { id: "a", label: "a[16]", status: "valid", region: "heap" },
        { id: "b", label: "b[16]", status: "valid", region: "heap" },
      ] },
      { caption: "A write to 'a' goes past its 16-byte bound.", code: "memset(a, 'X', 32); // overflow into b's header", blocks: [
        { id: "a", label: "a[16]", status: "overflowed", region: "heap" },
        { id: "b", label: "b[16]", status: "valid", region: "heap" },
      ] },
      { caption: "The allocator metadata just before block 'b' is overwritten.", blocks: [
        { id: "a", label: "a[16]", status: "overflowed", region: "heap" },
        { id: "b", label: "b's header corrupted", status: "corrupted", region: "heap" },
      ] },
      { caption: "The next malloc()/free() call reads the corrupted metadata and can crash or be exploited to write to an attacker-chosen address.", blocks: [
        { id: "a", label: "a[16]", status: "overflowed", region: "heap" },
        { id: "b", label: "allocator confused", status: "corrupted", region: "heap" },
      ] },
    ],
  },
];
