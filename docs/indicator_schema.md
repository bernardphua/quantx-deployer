# .quantx Indicator File Schema

Version: 1.0

## Overview

A `.quantx` file is a JSON file that defines a custom technical indicator for the QuantX platform. Once uploaded and validated, the indicator becomes available in:
- **Backtest engine** (sandbox execution)
- **Strategy Studio** (condition builder)
- **Live bot deployment** (injected into generated bot scripts)

## File Format

```json
{
  "quantx_indicator_version": "1.0",
  "indicator_id": "VORTEX",
  "name": "Vortex Indicator",
  "display_name": "Vortex",
  "description": "Trend identification using VM+ and VM- oscillators",
  "category": "trend",
  "output_type": "dual",
  "output_labels": ["vortex_plus", "vortex_minus"],
  "inputs": ["highs", "lows", "closes"],
  "params": [
    {"k": "period", "label": "Period", "type": "int", "default": 14, "min": 2, "max": 100}
  ],
  "warmup_bars": 15,
  "usage_example": "calc_vortex(highs, lows, closes, 14)",
  "source": "https://en.wikipedia.org/wiki/Vortex_indicator",
  "calc_code": [
    "def calc_vortex(highs, lows, closes, period=14):",
    "    n = len(closes)",
    "    vip = [None] * n",
    "    vim = [None] * n",
    "    for i in range(period, n):",
    "        vm_plus = sum(abs(highs[j] - lows[j-1]) for j in range(i-period+1, i+1))",
    "        vm_minus = sum(abs(lows[j] - highs[j-1]) for j in range(i-period+1, i+1))",
    "        tr_sum = sum(",
    "            max(highs[j] - lows[j], abs(highs[j] - closes[j-1]), abs(lows[j] - closes[j-1]))",
    "            for j in range(i-period+1, i+1)",
    "        )",
    "        if tr_sum > 0:",
    "            vip[i] = round(vm_plus / tr_sum, 4)",
    "            vim[i] = round(vm_minus / tr_sum, 4)",
    "    return vip, vim"
  ]
}
```

## Field Reference

### Required Fields

| Field | Type | Description |
|---|---|---|
| `quantx_indicator_version` | string | Schema version. Must be `"1.0"` |
| `indicator_id` | string | Unique ID. Must match `^[A-Z][A-Z0-9_]{1,29}$` (e.g. `"VORTEX"`, `"MY_RSI_V2"`) |
| `name` | string | Human-readable name |
| `calc_code` | string[] | Python function code, one line per array element. See Naming Convention below. |

### Optional Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `display_name` | string | same as name | Short label for UI display |
| `description` | string | `""` | What the indicator measures |
| `category` | string | `"custom"` | One of: `trend`, `momentum`, `volatility`, `volume`, `custom` |
| `output_type` | string | `"single"` | One of: `single`, `dual`, `triple`, `multi` |
| `output_labels` | string[] | `["main"]` | Names for each output series |
| `inputs` | string[] | `["closes"]` | Required input arrays. Valid: `closes`, `highs`, `lows`, `opens`, `volumes` |
| `params` | object[] | `[]` | Tunable parameters. Each has `k` (key), `label`, `type`, `default`, `min`, `max` |
| `warmup_bars` | int | auto-detected | Number of initial bars that will be `None` |
| `usage_example` | string | auto-generated | Example function call |
| `source` | string | `""` | URL or reference for the indicator's methodology |

## Naming Convention

The function defined in `calc_code` MUST be named:
```
calc_{indicator_id_lowercase}
```

Examples:
- `indicator_id: "VORTEX"` -> function: `calc_vortex`
- `indicator_id: "MY_RSI_V2"` -> function: `calc_my_rsi_v2`

## Function Contract

```python
def calc_example(closes, period=14):
    """
    Arguments:
      - Input arrays as declared in 'inputs' field (default: closes only)
      - Parameters as declared in 'params' field (with defaults)
    
    Returns:
      - single:  list of N values (same length as input)
      - dual:    tuple of 2 lists, each length N
      - triple:  tuple of 3 lists, each length N
      - multi:   tuple of M lists matching len(output_labels)
    
    Rules:
      - Return None for warmup bars (insufficient history)
      - No imports allowed (math is available globally)
      - numpy available as 'np' if installed
      - Must not modify input arrays
      - Must handle edge cases (division by zero, empty data)
    """
    n = len(closes)
    result = [None] * n
    for i in range(period, n):
        result[i] = some_calculation(closes, i, period)
    return result
```

## Security Restrictions

The following are **forbidden** in calc_code:
- `import`, `from` (no module imports)
- `open(`, `exec(`, `eval(`, `compile(` (no file/code execution)
- `os.`, `sys.`, `subprocess`, `shutil`, `pathlib` (no system access)
- `socket`, `requests.`, `urllib`, `http.` (no network access)
- `__import__`, `globals(`, `locals(`, `vars(` (no introspection)
- `getattr(`, `setattr(`, `delattr(` (no attribute manipulation)

Available builtins: `len`, `range`, `list`, `min`, `max`, `abs`, `sum`, `round`, `zip`, `enumerate`, `int`, `float`, `bool`, `str`, `isinstance`, `sorted`, `reversed`

Available modules: `math` (always), `numpy` as `np` (if installed)

## Validation Pipeline

When you upload a .quantx file, it goes through 7 stages:

1. **Required fields** - All required fields present and valid format
2. **Field types** - Optional fields have correct types
3. **ID collision** - Check if indicator already exists (built-in = blocked, custom = prompt overwrite)
4. **Security scan** - No forbidden tokens in code
5. **Syntax check** - Valid Python syntax
6. **Dry-run** - Executes against 200 bars of dummy data, validates output shape
7. **Success** - Returns preview values and detected warmup period

## AI Prompt Template

Use this prompt with Claude to generate .quantx files:

```
I need a .quantx indicator file for: [INDICATOR NAME]

Research the calculation methodology for this indicator, then implement it as a JSON file matching the QuantX .quantx schema.

Requirements:
1. The JSON must have these required fields: quantx_indicator_version ("1.0"), indicator_id (UPPER_SNAKE_CASE), name, calc_code (array of strings, one per line)
2. The function must be named calc_{indicator_id_lowercase}
3. Input arrays are plain Python lists (not numpy arrays)
4. Return None for warmup bars where insufficient history exists
5. For multi-output indicators, return a tuple of lists
6. NO imports - math module is available globally, numpy as np
7. calc_code must be an array of strings, one per line of code
8. Include params with sensible defaults, min, and max values
9. Specify the correct inputs (closes, highs, lows, opens, volumes)
10. Set output_type correctly (single/dual/triple)

Output ONLY the JSON file content, nothing else.
```

## Complete Working Example: Vortex Indicator

Save as `vortex.quantx`:

```json
{
  "quantx_indicator_version": "1.0",
  "indicator_id": "VORTEX",
  "name": "Vortex Indicator",
  "display_name": "Vortex",
  "description": "Identifies trend direction using VM+ and VM- oscillators based on true range. VM+ > VM- suggests uptrend, VM- > VM+ suggests downtrend.",
  "category": "trend",
  "output_type": "dual",
  "output_labels": ["vortex_plus", "vortex_minus"],
  "inputs": ["highs", "lows", "closes"],
  "params": [
    {"k": "period", "label": "Period", "type": "int", "default": 14, "min": 2, "max": 100}
  ],
  "warmup_bars": 15,
  "usage_example": "vip, vim = calc_vortex(highs, lows, closes, 14)",
  "source": "https://en.wikipedia.org/wiki/Vortex_indicator",
  "calc_code": [
    "def calc_vortex(highs, lows, closes, period=14):",
    "    n = len(closes)",
    "    vip = [None] * n",
    "    vim = [None] * n",
    "    for i in range(period, n):",
    "        vm_plus = sum(abs(highs[j] - lows[j-1]) for j in range(i-period+1, i+1))",
    "        vm_minus = sum(abs(lows[j] - highs[j-1]) for j in range(i-period+1, i+1))",
    "        tr_sum = sum(",
    "            max(highs[j] - lows[j], abs(highs[j] - closes[j-1]), abs(lows[j] - closes[j-1]))",
    "            for j in range(i-period+1, i+1)",
    "        )",
    "        if tr_sum > 0:",
    "            vip[i] = round(vm_plus / tr_sum, 4)",
    "            vim[i] = round(vm_minus / tr_sum, 4)",
    "    return vip, vim"
  ]
}
```

Upload this file in Settings > Custom Indicators > Upload .quantx to test.
