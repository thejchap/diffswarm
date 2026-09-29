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

## experimental Pierre viewer

Append `?experimental-pierre-rendering` to a diff URL to use the read-only
Pierre viewer. It supports unified and split layouts, syntax highlighting,
line numbers, and virtualized scrolling. The normal viewer remains available
through the page's **Open normal viewer** link.

This page loads only the stored raw patch. Comments, completion controls,
renaming, and search remain in the normal viewer. Omitted patch context cannot
be expanded without the original files.

The experiment uses `@pierre/diffs` 1.5.1 through pinned esm.sh imports and a
same-origin module worker entrypoint; it requires no frontend build step.

### local benchmark

Measured against commit `33ab09f` on an isolated September 29, 2026 production
database snapshot containing 19 diffs and 186,009 lines. The selected diff had
654 hunks and 38,127 lines. HTTP timings are the median of three localhost
requests without compression; they exclude browser module loading and rendering.

| Measurement             |   Before | Optimized normal viewer | Pierre viewer |
| ----------------------- | -------: | ----------------------: | ------------: |
| Full relation loader    |  18.35 s |                  0.49 s |    Not needed |
| Loader process peak RSS |  543 MiB |                 117 MiB |  Not measured |
| HTML first byte         |  15.78 s |                  0.91 s |       0.008 s |
| HTML response size      | 13.17 MB |                13.17 MB |       1.99 MB |

The full serialized diff before and after optimization had the same SHA-256.
Pierre parsed all 654 hunks; browser checks confirmed virtualized rendering
through the final line, including switching layouts and resizing.
