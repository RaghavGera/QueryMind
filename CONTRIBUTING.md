# Contributing to Text-to-SQL

Thank you for your interest in contributing to the Text-to-SQL project! This document provides guidelines for contributing to the project.

## 🎯 Project Goals

This project aims to create a production-ready natural language to SQL conversion system with:
- High accuracy in intent understanding
- Robust ambiguity detection
- Safe query generation
- Clear user feedback

## 🔧 Development Setup

### Prerequisites
- Python 3.8+
- MySQL 8.0+
- Git
- A code editor (VS Code recommended)

### Setup Steps

1. Fork and clone the repository
```bash
git clone <your-fork-url>
cd text-to-sql
```

2. Create a virtual environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies
```bash
pip install -r requirements.txt
```

4. Set up your environment
```bash
cp .env.example .env
# Edit .env with your credentials
```

5. Set up the database
```bash
psql -U postgres -d text_to_sql -f database/text_to_sql_database.sql
```

## 📝 Code Style

### Python Style Guide
- Follow PEP 8 guidelines
- Use type hints where possible
- Write descriptive docstrings for classes and functions
- Keep functions focused and small (<50 lines ideally)

### Example Function Format
```python
def function_name(param1: str, param2: int) -> Dict[str, Any]:
    """
    Brief description of what the function does.
    
    Args:
        param1: Description of param1
        param2: Description of param2
        
    Returns:
        Description of return value
        
    Raises:
        ValueError: Description of when this is raised
    """
    # Implementation
    pass
```

### Naming Conventions
- Classes: `PascalCase` (e.g., `AmbiguityDetector`)
- Functions/Methods: `snake_case` (e.g., `detect_ambiguities`)
- Constants: `UPPER_SNAKE_CASE` (e.g., `MAX_RETRIES`)
- Private methods: `_leading_underscore` (e.g., `_internal_method`)

## 🧪 Testing

### Writing Tests
- All new features must include tests
- Place tests in the `testing/` directory
- Name test files as `test_<feature>.py`
- Use descriptive test function names: `test_<what_is_being_tested>`

### Running Tests
```bash
# Run all tests
python testing/test_phase1.py
python testing/test_phase2.py
python testing/test_phase3.py

# Run specific test
python testing/test_phase3.py
```

### Test Structure
```python
def test_feature_name():
    """Test description."""
    # Setup
    detector = AmbiguityDetector(schema)
    
    # Execute
    result = detector.detect_ambiguities(intent)
    
    # Assert
    assert result.has_ambiguities == True
    assert len(result.ambiguities) > 0
```

## 🔀 Git Workflow

### Branch Naming
- Feature: `feature/description` (e.g., `feature/add-postgresql-support`)
- Bug fix: `bugfix/description` (e.g., `bugfix/fix-null-handling`)
- Documentation: `docs/description` (e.g., `docs/update-readme`)

### Commit Messages
Follow the conventional commits format:

```
<type>(<scope>): <subject>

<body>

<footer>
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

Example:
```
feat(ambiguity): add semantic ambiguity detection

- Added dictionary of ambiguous business terms
- Implemented context-aware suggestions
- Added tests for semantic detection

Closes #123
```

### Pull Request Process

1. **Create a branch** from `main`
```bash
git checkout -b feature/your-feature-name
```

2. **Make your changes** with clear commits

3. **Test your changes**
```bash
# Run relevant tests
python testing/test_*.py
```

4. **Update documentation** if needed
   - Update README.md for user-facing changes
   - Add/update docstrings for code changes
   - Add examples if introducing new features

5. **Push your branch**
```bash
git push origin feature/your-feature-name
```

6. **Create a Pull Request** with:
   - Clear title describing the change
   - Description of what was changed and why
   - Screenshots/examples if applicable
   - Reference to related issues

### PR Checklist
- [ ] Code follows project style guidelines
- [ ] All tests pass
- [ ] New tests added for new features
- [ ] Documentation updated
- [ ] Commit messages are clear
- [ ] No unnecessary files included

## 🐛 Reporting Bugs

### Before Reporting
1. Check existing issues to avoid duplicates
2. Test with the latest version
3. Verify it's reproducible

### Bug Report Template
```markdown
**Description**
Clear description of the bug

**To Reproduce**
Steps to reproduce:
1. ...
2. ...

**Expected Behavior**
What you expected to happen

**Actual Behavior**
What actually happened

**Environment**
- OS: [e.g., Windows 11]
- Python version: [e.g., 3.10]
- MySQL version: [e.g., 8.0]

**Additional Context**
Any other relevant information
```

## 💡 Feature Requests

We welcome feature suggestions! Please:

1. Check existing feature requests
2. Explain the use case clearly
3. Describe the expected behavior
4. Consider how it fits with existing features

### Feature Request Template
```markdown
**Feature Description**
Clear description of the feature

**Use Case**
Why is this feature needed?

**Proposed Solution**
How should this work?

**Alternatives Considered**
Other approaches you've thought about

**Additional Context**
Any other relevant information
```

## 📋 Current Focus Areas

We're particularly interested in contributions to:

### Phase 4: SQL Generation
- Converting structured intents to SQL
- Query optimization
- Multi-database support

### Phase 3 Enhancements
- Semantic ambiguity detection
- Advanced time reference handling
- Business logic validation

### Testing
- More real-world test cases
- Edge case coverage
- Performance benchmarks

### Documentation
- More usage examples
- Video tutorials
- API documentation

## 🤝 Code Review Process

All contributions go through code review:

1. **Automated checks** run on PR creation
2. **Maintainer review** within 2-3 days
3. **Feedback incorporation** as needed
4. **Approval and merge** when ready

### What Reviewers Look For
- Code correctness and quality
- Test coverage
- Documentation completeness
- Performance implications
- Security considerations

## 📞 Getting Help

- **Questions**: Open a GitHub Discussion
- **Bugs**: Open a GitHub Issue
- **Feature ideas**: Open a GitHub Issue with "Feature Request" label
- **Chat**: Join our community (link TBD)

## 🏆 Recognition

Contributors are recognized in:
- README.md contributors section
- Release notes
- Project documentation

Thank you for contributing! 🎉
