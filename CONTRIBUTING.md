# Contributing to DiscoSights

Thank you for your interest in contributing to DiscoSights.

## Reporting Issues

Please open a GitHub issue for:
- Bug reports (include Python version, error message, and steps to reproduce)
- Data quality concerns (incorrect county values, stale datasets)
- Feature requests

## Contributing Code

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run the test suite: `pytest tests/ -v`
5. Submit a pull request

## Running Tests

```bash
pip install -r requirements.txt
pytest tests/ -v
```

All 33 scientific tests must pass before any PR will be merged.

## Data Pipeline

The data pipeline requires Supabase credentials. See `.env.example` for required environment variables. Contact the maintainer for read-only access to the development database for testing.

## Scientific Contributions

If you identify a data quality issue, methodology concern, or validation improvement:
- Open an issue describing the concern
- Reference specific line numbers in `data/methods_note_draft.md` if applicable
- Include quantitative evidence where possible

## Code of Conduct

This project follows standard open source community standards. Be respectful, constructive, and evidence-based in all discussions.
