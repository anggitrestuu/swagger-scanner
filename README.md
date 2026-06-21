# Swagger Scanner

Simple Python CLI tool to scan OpenAPI v3 JSON and generate Markdown documentation with TypeScript interfaces.

## Installation

```bash
pip install -r requirements.txt
```

## Usage

```bash
python -m swagger_scanner <URL> -o <OUTPUT_DIR>
```

### Example

```bash
python -m swagger_scanner http://localhost:8000/openapi.json -o docs/api
```

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `-o, --output` | `./docs` | Output directory path |
| `--types-output` | - | Optional directory for generated `.ts` type modules. Omit this to generate Markdown only. |
| `--types-filename-style` | `tag` | Type filename style: `tag` keeps tag names, `singular` writes simple singular filenames like `events` -> `event.ts`. |
| `--types-any` | `unknown` | Fallback TypeScript type for unknown OpenAPI schemas in generated modules: `unknown` or `any`. |
| `--types-data-only` | `false` | Omit API response wrappers and shared API metadata/error schemas from generated `.ts` modules. |

### Generate Markdown and TypeScript Types

```bash
python -m swagger_scanner http://localhost:8000/openapi.json \
  -o docs/api \
  --types-output src/lib/api/providers/core/types \
  --types-filename-style singular \
  --types-data-only
```

`--types-output` is opt-in. By default, the scanner only writes Markdown files.

## Output

The tool generates a directory with:

- `index.md` - Index file with links to all modules
- `{tag}.md` - One file per API tag with endpoints table and TypeScript interfaces

### Example Output Structure

```
docs/api/
├── index.md
├── auth.md
├── users.md
├── orders.md
└── ...
```

### Output Format

Each tag file contains:

1. **API Endpoints Table** - Method, Endpoint, Description, Request Body, Response
2. **TypeScript Interfaces** - All related interfaces with property comments

## License

MIT
