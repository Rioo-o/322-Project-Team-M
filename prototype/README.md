# Prototype – Login / Sign In
**User Login** — the entry point for all roles (Student, Instructor, Registrar).

## Demo Credentials

| Role       | Email                      | Password |
|------------|----------------------------|----------|
| Student    | alice@college0.edu         | pass123  |
| Instructor | smith@college0.edu         | pass123  |
| Registrar  | registrar@college0.edu     | admin    |

Email + password + role selector form | User types: Registrar, Instructor, Student, Visitor
Credential validation with error message | Accepted new students receive a unique student id and password
Role mismatch detection (right email, wrong role) | Four distinct user roles
"Apply for Admission" link for visitors | A visitor can apply to be a student
"Apply as Instructor" link | A visitor can also apply to be an instructor
"Continue as Visitor" link | Visitors can browse some basic information
Enter-key submission | standard UX
Success screen showing name, ID, and role | login confirmation
