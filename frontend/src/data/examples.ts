export interface Example { name: string; vulnerable: boolean; code: string; }

export const EXAMPLES: Example[] = [
  {
    name: "Buffer Overflow (Vulnerable)",
    vulnerable: true,
    code: `/* Vulnerable: no bounds check on strcpy */
void copy_user_data(char *user_input) {
    char buffer[64];
    strcpy(buffer, user_input);   /* copies without checking length */
    process_data(buffer);
}`,
  },
  {
    name: "Bounds-Checked Copy (Safe)",
    vulnerable: false,
    code: `/* Safe: bounds-checked string copy */
void copy_user_data(char *user_input, size_t input_len) {
    char buffer[64];
    if (input_len >= sizeof(buffer)) {
        fprintf(stderr, "Input too large\\n");
        return;
    }
    strncpy(buffer, user_input, sizeof(buffer) - 1);
    buffer[sizeof(buffer) - 1] = '\\0';
    process_data(buffer);
}`,
  },
  {
    name: "Integer Overflow Risk (Vulnerable)",
    vulnerable: true,
    code: `/* Vulnerable: integer overflow in size calculation */
void allocate_array(int n, int m) {
    int *arr = (int *)malloc(n * m * sizeof(int));  /* n*m can overflow */
    if (arr == NULL) return;
    for (int i = 0; i < n * m; i++) {
        arr[i] = 0;
    }
    free(arr);
}`,
  },
  {
    name: "Null Pointer Dereference (Vulnerable)",
    vulnerable: true,
    code: `/* Vulnerable: return value of malloc not checked */
char *create_buffer(size_t size) {
    char *buf = (char *)malloc(size);
    buf[0] = '\\0';    /* crash if malloc returns NULL */
    return buf;
}`,
  },
  {
    name: "Null-Safe Allocation (Safe)",
    vulnerable: false,
    code: `/* Safe: malloc return value checked */
char *create_buffer(size_t size) {
    if (size == 0) return NULL;
    char *buf = (char *)malloc(size);
    if (buf == NULL) {
        perror("malloc failed");
        return NULL;
    }
    buf[0] = '\\0';
    return buf;
}`,
  },
  {
    name: "Complex Function with Loops (Vulnerable)",
    vulnerable: true,
    code: `/* Vulnerable: loop without bounds, pointer arithmetic errors */
int process_packets(unsigned char *data, int len) {
    int i, count = 0;
    unsigned char *ptr = data;
    for (i = 0; i < len; i++) {
        if (*ptr == 0xFF) {
            int size = *(ptr + 1);   /* unchecked read */
            memcpy(ptr + 2, data + count, size);  /* no bounds check */
            count += size;
            ptr += size + 2;
        } else {
            ptr++;
        }
    }
    return count;
}`,
  },
];
