# =============================================================================
# knowledge_base.py -- Static vulnerability knowledge base.
# Maps CWE categories (surfaced by the line-risk scanner in ml_bridge.py)
# to human-readable security guidance: description, impact, severity,
# example, mitigation, secure alternative, and reference CVEs.
# This is reference content, independent of the trained model.
# =============================================================================

KNOWLEDGE_BASE = {
    "CWE-120": {
        "id": "CWE-120",
        "name": "Buffer Copy without Checking Size of Input",
        "aka": "Classic Buffer Overflow",
        "severity": "Critical",
        "description": (
            "Data is copied into a fixed-size buffer without verifying that "
            "the source fits, allowing an attacker-controlled input to write "
            "past the end of the buffer."
        ),
        "impact": (
            "Memory corruption, crashes, and -- on stack buffers -- potential "
            "arbitrary code execution via return-address overwrite."
        ),
        "vulnerable_example": (
            "void copy(char *input) {\n"
            "    char buf[64];\n"
            "    strcpy(buf, input);  // no length check\n"
            "}"
        ),
        "secure_example": (
            "void copy(const char *input, size_t input_len) {\n"
            "    char buf[64];\n"
            "    if (input_len >= sizeof(buf)) return;\n"
            "    strncpy(buf, input, sizeof(buf) - 1);\n"
            "    buf[sizeof(buf) - 1] = '\\0';\n"
            "}"
        ),
        "mitigation": [
            "Use bounded functions: strncpy/strlcpy/snprintf instead of strcpy/strcat/sprintf.",
            "Always pass and check the destination buffer size.",
            "Prefer dynamically sized buffers (with explicit bounds) over fixed stack arrays for untrusted input.",
            "Compile with stack protection (-fstack-protector-strong) and FORTIFY_SOURCE.",
        ],
        "cve_examples": ["CVE-2021-3156 (Sudo Baron Samedit)", "CVE-2014-0160 (Heartbleed, related overread)", "CVE-2019-11477 (Linux TCP SACK)"] ,
    },
    "CWE-242": {
        "id": "CWE-242",
        "name": "Use of Inherently Dangerous Function",
        "aka": "gets()",
        "severity": "Critical",
        "description": "gets() reads a line of input with no way to bound its length, making overflow unavoidable for any sufficiently long input.",
        "impact": "Guaranteed stack buffer overflow given attacker-controlled input length.",
        "vulnerable_example": "char buf[128];\ngets(buf); // impossible to use safely",
        "secure_example": "char buf[128];\nfgets(buf, sizeof(buf), stdin);",
        "mitigation": [
            "Never use gets() -- it was removed from the C11 standard.",
            "Use fgets() with an explicit buffer size, or getline() on POSIX systems.",
        ],
        "cve_examples": ["CVE-1999-0231 (early gets() based overflows)"] ,
    },
    "CWE-190": {
        "id": "CWE-190",
        "name": "Integer Overflow or Wraparound",
        "aka": "Integer Overflow",
        "severity": "High",
        "description": "An arithmetic operation (often a size calculation feeding malloc) can exceed the maximum value the integer type can hold and silently wrap around to a small or negative number.",
        "impact": "Undersized allocation followed by a buffer overflow when the code writes using the original (large) size.",
        "vulnerable_example": "int *arr = malloc(n * m * sizeof(int)); // n*m may overflow",
        "secure_example": (
            "if (n <= 0 || m <= 0 || n > SIZE_MAX / m / sizeof(int)) return NULL;\n"
            "int *arr = malloc((size_t)n * m * sizeof(int));"
        ),
        "mitigation": [
            "Validate multiplicands before multiplying, or use built-in overflow checks (__builtin_mul_overflow).",
            "Use size_t consistently for sizes, and check against SIZE_MAX.",
            "Prefer calloc(n, size) which checks for overflow internally on most libc implementations.",
        ],
        "cve_examples": ["CVE-2016-6187 (Linux kernel integer overflow)", "CVE-2002-0392 (Apache chunked encoding)"] ,
    },
    "CWE-770": {
        "id": "CWE-770",
        "name": "Allocation of Resources Without Limits or Throttling",
        "aka": "Unbounded alloca()",
        "severity": "High",
        "description": "alloca() allocates on the stack with a caller-controlled size and no bounds check, risking stack exhaustion.",
        "impact": "Stack overflow / crash, and on some platforms exploitable memory corruption.",
        "vulnerable_example": "void f(size_t n) {\n    char *buf = alloca(n); // n from network input\n}",
        "secure_example": "void f(size_t n) {\n    if (n > MAX_STACK_ALLOC) return;\n    char *buf = alloca(n);\n}",
        "mitigation": [
            "Bound the size passed to alloca(), or use heap allocation with proper error handling instead.",
            "Consider VLA/alloca-free rewrites for anything driven by external input.",
        ],
        "cve_examples": ["CVE-2017-1000366 (glibc stack clash)"],
    },
    "CWE-416": {
        "id": "CWE-416",
        "name": "Use After Free",
        "aka": "UAF / Double Free",
        "severity": "Critical",
        "description": "Memory is referenced after it has been freed, or freed more than once, because the pointer was not reset to NULL after free().",
        "impact": "Memory corruption; frequently exploitable for arbitrary code execution when the freed memory is reallocated and attacker-controlled.",
        "vulnerable_example": "free(ptr);\n... \nptr->value = 1; // use after free",
        "secure_example": "free(ptr);\nptr = NULL;\n...\nif (ptr) ptr->value = 1;",
        "mitigation": [
            "Set pointers to NULL immediately after free().",
            "Use RAII-style ownership patterns or a single clear owner for each allocation.",
            "Enable AddressSanitizer during testing to catch UAF and double-free automatically.",
        ],
        "cve_examples": ["CVE-2021-30632 (V8 UAF)", "CVE-2019-5786 (Chrome FileReader UAF)"] ,
    },
    "CWE-134": {
        "id": "CWE-134",
        "name": "Use of Externally-Controlled Format String",
        "aka": "Format String Vulnerability",
        "severity": "Critical",
        "description": "User-controlled data is passed as the format string itself (e.g. printf(input)) instead of as an argument, allowing %n, %s, %x to read or write arbitrary memory.",
        "impact": "Information disclosure (stack reads) up to arbitrary memory write and code execution via %n.",
        "vulnerable_example": "printf(user_input); // user_input may contain %n",
        "secure_example": "printf(\"%s\", user_input);",
        "mitigation": [
            "Never pass untrusted data as a format string; always use a fixed format with the data as an argument.",
            "Compile with -Wformat -Wformat-security and treat warnings as errors.",
        ],
        "cve_examples": ["CVE-2000-0573 (wu-ftpd format string)", "CVE-2012-0809 (sudo format string)"] ,
    },
    "CWE-78": {
        "id": "CWE-78",
        "name": "OS Command Injection",
        "aka": "Command Injection",
        "severity": "Critical",
        "description": "Unsanitised input is passed to system()/exec*() and interpreted by a shell, letting an attacker append arbitrary commands.",
        "impact": "Full command execution in the context of the running process.",
        "vulnerable_example": "char cmd[256];\nsprintf(cmd, \"ping %s\", user_host);\nsystem(cmd);",
        "secure_example": "execvp(\"ping\", (char*[]){\"ping\", \"-c\", \"1\", user_host, NULL});",
        "mitigation": [
            "Avoid system()/popen() with any externally influenced string.",
            "Use exec* family with an explicit argv array (no shell interpretation).",
            "Strictly allow-list input before it ever reaches a subprocess call.",
        ],
        "cve_examples": ["CVE-2021-44228 (Log4Shell, related class)", "CVE-2014-6271 (Shellshock)"] ,
    },
    "CWE-170": {
        "id": "CWE-170",
        "name": "Improper Null Termination",
        "aka": "Missing NUL Terminator",
        "severity": "Medium",
        "description": "strncpy() does not NUL-terminate the destination if the source is exactly as long as (or longer than) the size argument.",
        "impact": "Subsequent string operations read past the buffer, leaking memory or crashing.",
        "vulnerable_example": "char buf[16];\nstrncpy(buf, src, sizeof(buf)); // may not terminate",
        "secure_example": "char buf[16];\nstrncpy(buf, src, sizeof(buf) - 1);\nbuf[sizeof(buf) - 1] = '\\0';",
        "mitigation": [
            "Always reserve the last byte for the NUL terminator and set it explicitly.",
            "Prefer strlcpy() where available.",
        ],
        "cve_examples": ["CVE-2015-3210 (various strncpy misuse reports)"] ,
    },
    "CWE-125": {
        "id": "CWE-125",
        "name": "Out-of-bounds Read",
        "aka": "Buffer Over-read",
        "severity": "High",
        "description": "An index or pointer is advanced inside a subscript expression without a visible bound check, risking a read past the end of the buffer.",
        "impact": "Information disclosure, crashes, or a pivot toward further memory corruption.",
        "vulnerable_example": "for (i = 0; ; i++) {\n    if (data[i++] == 0xFF) break; // no upper bound\n}",
        "secure_example": "for (i = 0; i < len; i++) {\n    if (data[i] == 0xFF) break;\n}",
        "mitigation": [
            "Always pair pointer/index advancement with an explicit upper bound check.",
            "Use size-carrying slices/spans instead of raw pointers where possible.",
        ],
        "cve_examples": ["CVE-2014-0160 (Heartbleed)"] ,
    },
    "CWE-476": {
        "id": "CWE-476",
        "name": "NULL Pointer Dereference",
        "aka": "Null Deref",
        "severity": "Medium",
        "description": "A pointer returned from an allocation or lookup function is dereferenced without first checking it for NULL.",
        "impact": "Crash (denial of service); in kernel/embedded contexts can be more severe.",
        "vulnerable_example": "char *buf = malloc(size);\nbuf[0] = 0; // crash if malloc failed",
        "secure_example": "char *buf = malloc(size);\nif (!buf) return NULL;\nbuf[0] = 0;",
        "mitigation": [
            "Check the return value of every allocation and lookup function before use.",
            "Adopt a consistent error-handling convention (goto cleanup, early return) so checks aren't skipped.",
        ],
        "cve_examples": ["CVE-2020-8835 (Linux kernel eBPF null deref class)"] ,
    },
}

DEFAULT_ENTRY = {
    "id": "CWE-Other",
    "name": "General Memory-Safety Concern",
    "aka": "Uncategorised",
    "severity": "Info",
    "description": "This pattern did not match a specific catalogued CWE but is flagged by the heuristic scanner as worth a manual look.",
    "impact": "Varies -- manual review recommended.",
    "vulnerable_example": "",
    "secure_example": "",
    "mitigation": ["Perform a manual security review of this code path."],
    "cve_examples": [],
}


# =============================================================================
# Knowledge Center enrichment (additive) -- CVSS baseline scores, MITRE/OWASP
# reference links, and notable real-world incidents per CWE. Kept as a
# separate lookup so the core KNOWLEDGE_BASE entries above stay untouched.
# CVSS scores below are the published NVD "base score" ranges typical for
# each weakness class (illustrative baseline, not a per-instance CVSS
# calculation -- an actual finding's score depends on the specific context).
# =============================================================================

_ENRICHMENT = {
    "CWE-120": {
        "cvss": {"score": 9.8, "vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"},
        "real_attacks": [
            "Morris Worm (1988) -- one of the first internet-scale incidents, driven by a stack buffer overflow in fingerd.",
            "Sudo 'Baron Samedit' (CVE-2021-3156) -- heap buffer overflow in sudo allowing local privilege escalation to root.",
        ],
        "mitre_url": "https://cwe.mitre.org/data/definitions/120.html",
        "owasp_url": "https://owasp.org/www-community/vulnerabilities/Buffer_Overflow",
        "cert_c": {"id": "STR31-C", "title": "Guarantee that storage for strings has sufficient space for character data and the null terminator"},
        "capec": {"id": "CAPEC-100", "name": "Overflow Buffers"},
    },
    "CWE-242": {
        "cvss": {"score": 9.8, "vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"},
        "real_attacks": ["Historic Unix/BSD utilities compiled with gets() were a recurring source of remote root exploits through the 1990s, prompting its removal from C11."],
        "mitre_url": "https://cwe.mitre.org/data/definitions/242.html",
        "owasp_url": "https://owasp.org/www-community/vulnerabilities/Buffer_Overflow",
        "cert_c": {"id": "MSC24-C", "title": "Do not use deprecated or obsolete functions (gets() was removed from C11)"},
        "capec": {"id": "CAPEC-100", "name": "Overflow Buffers"},
    },
    "CWE-190": {
        "cvss": {"score": 8.1, "vector": "CVSS:3.1/AV:N/AC:H/PR:N/UI:N/S:U/C:H/I:H/A:H"},
        "real_attacks": [
            "CVE-2016-6187 -- Linux kernel integer overflow leading to heap buffer overflow and local privilege escalation.",
            "Android 'Stagefright' (2015) -- integer overflows in media parsing led to remote code execution via MMS.",
        ],
        "mitre_url": "https://cwe.mitre.org/data/definitions/190.html",
        "owasp_url": "https://owasp.org/www-community/vulnerabilities/Integer_overflow",
        "cert_c": {"id": "INT30-C", "title": "Ensure that unsigned integer operations do not wrap"},
        "capec": {"id": "CAPEC-92", "name": "Forced Integer Overflow"},
    },
    "CWE-770": {
        "cvss": {"score": 7.5, "vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:H"},
        "real_attacks": ["'Stack Clash' (CVE-2017-1000366) -- a class of glibc/kernel flaws around unbounded stack-adjacent allocations, enabling privilege escalation across multiple Linux utilities."],
        "mitre_url": "https://cwe.mitre.org/data/definitions/770.html",
        "owasp_url": "https://owasp.org/www-community/Denial_of_Service",
        "cert_c": {"id": "MEM05-C", "title": "Avoid large stack allocations"},
        "capec": None,
    },
    "CWE-416": {
        "cvss": {"score": 8.8, "vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:R/S:U/C:H/I:H/A:H"},
        "real_attacks": [
            "CVE-2019-5786 -- Chrome FileReader use-after-free, exploited in the wild for remote code execution.",
            "CVE-2021-30632/30633 -- V8 and Chrome UAF bugs actively exploited as zero-days.",
        ],
        "mitre_url": "https://cwe.mitre.org/data/definitions/416.html",
        "owasp_url": "https://owasp.org/www-community/vulnerabilities/Using_freed_memory",
        "cert_c": {"id": "MEM30-C", "title": "Do not access freed memory"},
        "capec": {"id": "CAPEC-129", "name": "Pointer Manipulation"},
    },
    "CWE-134": {
        "cvss": {"score": 9.8, "vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"},
        "real_attacks": ["wu-ftpd format string vulnerability (2000) -- allowed remote attackers to execute arbitrary code on a huge fraction of internet FTP servers at the time."],
        "mitre_url": "https://cwe.mitre.org/data/definitions/134.html",
        "owasp_url": "https://owasp.org/www-community/attacks/Format_string_attack",
        "cert_c": {"id": "FIO30-C", "title": "Exclude user input from format strings"},
        "capec": {"id": "CAPEC-135", "name": "Format String Injection"},
    },
    "CWE-78": {
        "cvss": {"score": 9.8, "vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"},
        "real_attacks": ["Shellshock (CVE-2014-6271) -- Bash environment-variable command injection affecting an enormous share of internet-facing Linux/Unix systems, actively mass-exploited within hours of disclosure."],
        "mitre_url": "https://cwe.mitre.org/data/definitions/78.html",
        "owasp_url": "https://owasp.org/www-community/attacks/Command_Injection",
        "cert_c": {"id": "ENV33-C", "title": "Do not call system()"},
        "capec": {"id": "CAPEC-88", "name": "OS Command Injection"},
    },
    "CWE-170": {
        "cvss": {"score": 5.9, "vector": "CVSS:3.1/AV:N/AC:H/PR:N/UI:N/S:U/C:N/I:N/A:H"},
        "real_attacks": ["Recurring root cause of information-disclosure bugs across embedded/IoT firmware where strncpy() results are trusted to be NUL-terminated."],
        "mitre_url": "https://cwe.mitre.org/data/definitions/170.html",
        "owasp_url": "https://owasp.org/www-community/vulnerabilities/Buffer_Overflow",
        "cert_c": {"id": "STR32-C", "title": "Do not pass a non-null-terminated character sequence to a library function that expects a string"},
        "capec": None,
    },
    "CWE-125": {
        "cvss": {"score": 7.5, "vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:N/A:N"},
        "real_attacks": ["Heartbleed (CVE-2014-0160) -- an out-of-bounds read in OpenSSL's heartbeat extension leaked private keys and credentials from a large fraction of HTTPS servers."],
        "mitre_url": "https://cwe.mitre.org/data/definitions/125.html",
        "owasp_url": "https://owasp.org/www-community/vulnerabilities/Out-of-bounds_Read",
        "cert_c": {"id": "ARR30-C", "title": "Do not form or use out-of-bounds pointers or array subscripts"},
        "capec": {"id": "CAPEC-540", "name": "Overread Buffers"},
    },
    "CWE-476": {
        "cvss": {"score": 5.5, "vector": "CVSS:3.1/AV:L/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:H"},
        "real_attacks": ["A leading root cause of denial-of-service CVEs across network daemons and kernel drivers -- an unchecked pointer from a failed lookup or allocation reaching a live code path."],
        "mitre_url": "https://cwe.mitre.org/data/definitions/476.html",
        "owasp_url": "https://owasp.org/www-community/vulnerabilities/Null_Dereference",
        "cert_c": {"id": "EXP34-C", "title": "Do not dereference null pointers"},
        "capec": None,
    },
}

_DEFAULT_ENRICHMENT = {
    "cvss": {"score": None, "vector": None},
    "real_attacks": [],
    "mitre_url": "https://cwe.mitre.org/data/definitions/1000.html",
    "owasp_url": "https://owasp.org/www-project-top-ten/",
    "cert_c": None,
    "capec": None,
}

CERT_C_CATALOG_URL = "https://wiki.sei.cmu.edu/confluence/display/c/SEI+CERT+C+Coding+Standard"
CAPEC_CATALOG_URL = "https://capec.mitre.org/"


def _enrich(entry: dict) -> dict:
    extra = _ENRICHMENT.get(entry["id"], _DEFAULT_ENRICHMENT)
    return {**entry, **extra}


def lookup(cwe_id: str) -> dict:
    entry = KNOWLEDGE_BASE.get(cwe_id, {**DEFAULT_ENTRY, "id": cwe_id})
    return _enrich(entry)


def all_entries() -> list:
    return [_enrich(e) for e in KNOWLEDGE_BASE.values()]
