# Text-to-SQL Project

A comprehensive natural language to SQL query conversion system with ambiguity detection and clarification.

## 🎯 Project Overview

This system converts natural language questions into SQL queries through a multi-phase pipeline that includes:
- Database schema introspection
- Natural language understanding
- Ambiguity detection and clarification
- SQL query generation (Phase 4 - Coming Soon)

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Natural Language Query                    │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│  Phase 1: Database Schema Introspection                     │
│  • Analyze database structure                                │
│  • Extract tables, columns, relationships                    │
│  • Identify foreign keys and constraints                     │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│  Phase 2: Natural Language Understanding                     │
│  • Entity Recognition (tables, columns, values)             │
│  • Intent Extraction (SELECT, COUNT, JOIN, etc.)            │
│  • Structured Intent Creation                                │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│  Phase 3: Ambiguity Detection & Clarification ✓             │
│  • Detect dangerous queries (DELETE without WHERE)          │
│  • Identify unclear references                               │
│  • Generate clarification questions                          │
│  • Provide resolution options                                │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│  Phase 4: SQL Generation (Coming Soon)                      │
│  • Convert structured intent to SQL                          │
│  • Apply optimizations                                       │
│  • Validate query syntax                                     │
└─────────────────────┬───────────────────────────────────────┘
                      │
                  SQL Query
```

## 📁 Project Structure

```
text-to-sql/
├── app/                          # Main application code
│   ├── __init__.py
│   ├── database.py               # Database connection & management
│   ├── schema.py                 # Schema introspection (Phase 1)
│   ├── entity_recognizer.py     # Entity recognition (Phase 2)
│   ├── intent_extractor.py      # Intent extraction (Phase 2)
│   ├── models.py                 # Pydantic data models
│   ├── openai_client.py          # OpenAI/Groq API client
│   └── ambiguity_detector.py    # Ambiguity detection (Phase 3)
│
├── testing/                      # Test suites
│   ├── test_phase1.py           # Phase 1 tests
│   ├── test_phase2.py           # Phase 2 tests
│   ├── test_phase3.py           # Phase 3 tests
│   └── test_ambiguity_realworld.py  # Real-world question tests
│
├── database/                     # Database setup
│   └── text_to_sql_database.sql # Sample database schema
│
├── benchmark/                    # Benchmarks and test data
│   └── text_to_sql_benchmark_with_sql.xlsx
│
├── docs/                         # Documentation
│   ├── PHASE3_README.md         # Phase 3 documentation
│   └── PHASE3_REALWORLD_RESULTS.md  # Test results
│
├── .env.example                 # Environment variables template
├── .gitignore                   # Git ignore rules
├── requirements.txt             # Python dependencies
├── README.md                    # This file
└── SETUP.md                     # Setup instructions
```

## ✨ Features

### Phase 1: Database Schema Introspection ✅
- Automatic schema analysis
- Foreign key relationship detection
- Data type identification
- Primary key discovery

### Phase 2: Natural Language Understanding ✅
- Entity recognition with fuzzy matching
- Intent extraction using LLM
- Structured intent creation
- Confidence scoring

### Phase 3: Ambiguity Detection ✅
- **10 Ambiguity Types Detected:**
  - Missing required filters (DELETE/UPDATE without WHERE)
  - Multiple table/column matches
  - Unclear relationships
  - Ambiguous time references
  - Implicit aggregations
  - Unclear ordering
  - Multiple join paths
  - And more...

- **4 Severity Levels:**
  - 🔴 CRITICAL: Must resolve (prevents data loss)
  - 🟠 HIGH: Should resolve (prevents wrong results)
  - 🟡 MEDIUM: Recommended (improves clarity)
  - 🟢 LOW: Optional (nice to have)

### Phase 4: SQL Generation 🚧
Coming soon...

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- MySQL 8.0+
- Groq API key (for LLM-based features)

### Installation

1. **Clone the repository**
```bash
git clone <repository-url>
cd text-to-sql
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Set up database**
```bash
psql -U postgres -d text_to_sql -f database/text_to_sql_database.sql
```

4. **Configure environment**
```bash
cp .env.example .env
# Edit .env with your credentials
```

5. **Run tests**
```bash
# Test Phase 1
python testing/test_phase1.py

# Test Phase 2
python testing/test_phase2.py

# Test Phase 3
python testing/test_phase3.py

# Test with real-world questions
python testing/test_ambiguity_realworld.py
```

## 📊 Test Results

### Phase 1 Tests
✅ 5/5 tests passing
- Database connection
- Schema introspection
- Table detection
- Column analysis
- Foreign key relationships

### Phase 2 Tests
✅ 5/5 tests passing
- OpenAI client initialization
- Entity recognition
- Intent extraction
- Full pipeline integration
- Pydantic models

### Phase 3 Tests
✅ 9/9 tests passing
- Ambiguity detector initialization
- Missing filter detection
- Column ambiguity detection
- Relationship ambiguity detection
- Implicit aggregation detection
- Unclear ordering detection
- Ambiguity resolution
- Comprehensive analysis
- Severity level classification

### Real-World Question Tests
✅ 10/10 questions analyzed successfully
- 40% detected ambiguities requiring clarification
- 100% accuracy on safety checks
- 0 false negatives on dangerous queries

## 🔧 Configuration

### Environment Variables (.env)

```env
# Database Configuration
DB_HOST=localhost
DB_PORT=5432
DB_USER=postgres
DB_PASSWORD=your_password
DB_NAME=text_to_sql

# Groq API Configuration
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=llama-3.1-70b-versatile
```

### API Keys

Get a free Groq API key:
1. Visit https://console.groq.com/keys
2. Sign up for an account
3. Generate an API key
4. Add it to your .env file

## 📖 Usage Examples

### Example 1: Basic Query
```python
from app.database import init_db
from app.schema import SchemaIntrospector
from app.ambiguity_detector import AmbiguityDetector
from app.models import StructuredIntent, QueryType

# Setup
db = init_db()
schema = SchemaIntrospector(db).introspect()
detector = AmbiguityDetector(schema)

# Create intent
intent = StructuredIntent(
    query_type=QueryType.SELECT,
    tables=["customers"],
    columns=["name", "email"],
    original_question="Get customer names and emails"
)

# Check for ambiguities
result = detector.detect_ambiguities(intent)

if result.can_proceed:
    print("✓ Query is clear, ready for SQL generation")
else:
    print("⚠ Ambiguities detected:")
    for amb in result.ambiguities:
        print(f"  - {amb.clarification_question}")
```

### Example 2: Dangerous Query Detection
```python
# Dangerous DELETE without WHERE
intent = StructuredIntent(
    query_type=QueryType.DELETE,
    tables=["customers"],
    original_question="Delete customers"
)

result = detector.detect_ambiguities(intent)
# Output: CRITICAL - "Are you sure you want to delete ALL rows?"
```

## 🧪 Testing

### Run All Tests
```bash
# Run all phase tests sequentially
python testing/test_phase1.py && \
python testing/test_phase2.py && \
python testing/test_phase3.py
```

### Run Specific Tests
```bash
# Phase 1 only
python testing/test_phase1.py

# Phase 2 only (requires Groq API key)
python testing/test_phase2.py

# Phase 3 only
python testing/test_phase3.py

# Real-world questions
python testing/test_ambiguity_realworld.py
```

## 📚 Documentation

- [Setup Guide](SETUP.md) - Detailed setup instructions
- [Phase 3 Documentation](docs/PHASE3_README.md) - Ambiguity detection details
- [Phase 3 Test Results](docs/PHASE3_REALWORLD_RESULTS.md) - Real-world test analysis

## 🛣️ Roadmap

- [x] Phase 1: Database Schema Introspection
- [x] Phase 2: Natural Language Understanding
- [x] Phase 3: Ambiguity Detection & Clarification
- [ ] Phase 4: SQL Query Generation
- [ ] Phase 5: Query Optimization
- [ ] Phase 6: Result Interpretation
- [ ] Web UI Interface
- [ ] API Endpoints
- [ ] Multi-database support (PostgreSQL, SQLite)

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📝 License

This project is licensed under the MIT License.

## 👤 Author

Raghav

## 🙏 Acknowledgments

- OpenAI/Groq for LLM capabilities
- Pydantic for data validation
- MySQL for database support

---

**Status**: Phase 3 Complete ✅ | Phase 4 In Progress 🚧

Last Updated: 2026-08-27
