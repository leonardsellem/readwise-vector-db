# Testing Strategy

This document outlines our testing approach and coverage requirements.

## Targeted Coverage Strategy

We use a **targeted coverage approach** instead of a blanket coverage
percentage, focusing testing effort where it matters most:

### Coverage Tiers

| **Tier** | **Modules** | **Required Coverage** | **Rationale** |
|----------|-------------|----------------------|---------------|
| **Core** | `core/`, `db/`, `models/` | **90%** | Business-critical logic |
| **High-Priority** | `api/`, `jobs/` | **75%** | User-facing features |
| **Standard** | `mcp/`, `config/`, `main/` | **60%** | Supportive components |

### Why Targeted Coverage?

1. **Focus on Critical Paths**: Core modules contain complex algorithms
   (embedding, search, database operations) where bugs have the highest impact
2. **Realistic Standards**: Different modules have different testing needs -
   volatile code shouldn't require the same coverage as stable core logic
3. **Developer Efficiency**: Spend testing effort where it provides the most
   value

### Local Development

```bash
# Run tests with targeted coverage validation
make cov

# This runs:
# 1. pytest with coverage collection
# 2. coverage json export
# 3. Our custom checker script that validates per-module thresholds
```

### CI Integration

Our GitHub Actions workflow automatically validates these thresholds on every
push and pull request. The build fails if any tier doesn't meet its target.

## Migration from Global Coverage

**Before**: Single 90% threshold across all code
**After**: Tiered approach (90% core, 75% high-priority, 60% standard)

This change allows us to:

- Maintain high standards for critical code
- Be more pragmatic about supportive modules
- Focus testing effort more strategically

## Coverage Tools

- **`tools/coverage_buckets.py`**: Module categorization and thresholds
- **`tools/check_coverage.py`**: Validation script with colored output
- **`make cov`**: Developer-friendly local testing command

## Writing Tests

### Core Modules (90% target)

- Test all major code paths
- Include edge cases and error scenarios
- Mock external dependencies
- Test both success and failure cases

### High-Priority Modules (75% target)

- Focus on user-facing functionality
- Test main workflows and integrations
- Include basic error handling

### Standard Modules (60% target)

- Test core functionality
- May skip some edge cases
- Focus on preventing regressions
