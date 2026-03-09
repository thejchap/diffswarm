# diffswarm

https://diffswarm.dev/

github-style review and workflow for any unified diff

```bash
diff <(echo "foo") <(echo "foo\nbar") -u | curl -X POST --data-binary @- https://diffswarm.dev
```

<img width="1153" height="644" alt="Screenshot 2026-03-08 at 23 20 08" src="https://github.com/user-attachments/assets/f0ef7864-17a6-42db-b9c3-af6da6645e6e" />

## getting started

```sh
docker compose up --build
```

the app will be available at `http://localhost:8000`.
