# Architecture Overview

This project follows a **layered architecture** pattern with clear separation of concerns.

## Layers

### 1. Repository Layer
- Handles direct database operations (CRUD).
- Returns database models or query results.
- Example: `UserRepository` interacts with the `users` table.

### 2. Service Layer
- Contains business logic.
- Uses repositories to fetch/modify data.
- Example: `UserService` hashes passwords before creating a user.

### 3. Route / Controller Layer
- Exposes HTTP endpoints.
- Calls service methods and returns responses.
- Example: `user_routes.py` defines `/users/` endpoints.

## Data Flow
```bash
HTTP Request → Route → Service → Repository → Database
HTTP Response ← Route ← Service ← Repository
```

## Benefits
- Separation of concerns
- Easier testing
- Scalable and maintainable
