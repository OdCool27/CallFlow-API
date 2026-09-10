# CallFlow API

CallFlow API is a lightweight telephony call-management backend built with Python, FastAPI, SQLAlchemy, and SQLite.

The project was created to demonstrate backend API development, relational database integration, request validation, reporting, automated testing, and exposure to Microsoft SQL Server / T-SQL concepts.

## Features

- Customer management
- Agent management
- Telephony call tracking
- Call status updates
- Agent-based call filtering
- Reporting and call statistics
- SQL aggregation
- SQLAlchemy ORM integration
- Request and response validation with Pydantic
- Automated API testing with pytest
- T-SQL reporting queries and stored procedure examples

---

## Technology Stack

### Backend
- Python
- FastAPI
- Pydantic
- Uvicorn

### Database
- SQLAlchemy ORM
- SQLite for the working application
- Microsoft SQL Server / T-SQL practice scripts

### Testing
- pytest
- FastAPI TestClient

### Development
- PyCharm
- Git
- GitHub

---

## Architecture

The application follows a simple layered backend structure:

Client
|
v
FastAPI Routes
|
v
Pydantic Schemas
|
v
Application / Business Logic
|
v
SQLAlchemy ORM
|
v
Relational Database

FastAPI handles the HTTP layer and routing.

Pydantic handles request and response validation.

SQLAlchemy maps Python objects to relational database tables.

SQLite is used as the development database.

Additional T-SQL scripts demonstrate equivalent SQL Server reporting and stored-procedure concepts.

---

## Project Structure

callflow-api/
|
├── app/
│   ├── routers/
│   │   ├── customers.py
│   │   ├── agents.py
│   │   ├── calls.py
│   │   └── reports.py
│   │
│   ├── database.py
│   ├── main.py
│   ├── models.py
│   └── schemas.py
│
├── tests/
│   └── test_main.py
│
├── sql/
│   └── procedures.sql
│
├── requirements.txt
├── .gitignore
└── README.md

---

## Database Model

### Customer

Represents a customer involved in one or more calls.

Fields:

- id
- name
- phone_number
- email

Relationship:

A customer can have many calls.

### Agent

Represents an employee or call-center agent.

Fields:

- id
- name
- extension
- department

Relationship:

An agent can handle many calls.

### Call

Represents a telephony call between a customer and an agent.

Fields:

- id
- customer_id
- agent_id
- direction
- status
- started_at
- ended_at
- notes

Relationships:

Customer 1 --- * Call

Agent 1 --- * Call

---

## API Endpoints

### Customers

| Method | Endpoint | Description |
|---|---|---|
| POST | /customers | Create a customer |
| GET | /customers | Retrieve all customers |
| GET | /customers/{id} | Retrieve a customer |

### Agents

| Method | Endpoint | Description |
|---|---|---|
| POST | /agents | Create an agent |
| GET | /agents | Retrieve all agents |
| GET | /agents/{id} | Retrieve an agent |

### Calls

| Method | Endpoint | Description |
|---|---|---|
| POST | /calls | Create a call |
| GET | /calls | Retrieve calls |
| GET | /calls/{id} | Retrieve a specific call |
| PATCH | /calls/{id} | Update or complete a call |
| DELETE | /calls/{id} | Delete a call |

Calls can also be filtered with query parameters.

Examples:

GET /calls?status=COMPLETED

GET /calls?agent_id=1

GET /calls?status=COMPLETED&agent_id=1

### Reports

| Method | Endpoint | Description |
|---|---|---|
| GET | /reports/agents | Retrieve total calls per agent |
| GET | /reports/agents/{id}/statistics | Retrieve statistics for an agent |

Agent statistics include:

- total calls
- completed calls
- average call duration

---

## Example Request

### Create Customer

POST /customers

```json
{
  "name": "John Brown",
  "phone_number": "876-555-1234",
  "email": "john@example.com"
}