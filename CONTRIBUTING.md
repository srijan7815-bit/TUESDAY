# Contributing

1. Create a branch from `main`.
2. Copy `.env.example` to `.env`; never commit the result.
3. Install `services/api/requirements-dev.txt` in a Python 3.12 virtual environment.
4. Run `./scripts/check.sh` before opening a pull request.
5. Keep external service calls behind the existing provider adapters and add tests for authorization, failure behavior, and input limits.

Pull requests must pass backend, web, Android, and Linux jobs. A change is not considered verified against NVIDIA, E2B, Fish Audio, or Render unless the relevant live credential test or deployment check was actually run.
