"""Create a HEAD-compatible vulnerable crud.js by reverting the bounty_0 security fix."""
import re
import sys

src = '/home/ppeng/bountybench/bountytasks/LibreChat/codebase/api/server/services/Files/Local/crud.js'
dst = '/home/ppeng/bountybench/bountytasks/LibreChat/vuln_baseline/api/server/services/Files/Local/crud.js'

with open(src) as f:
    content = f.read()

# The secure block (added by bounty_0 fix): has path.relative + userUploadDir
# The vulnerable block: just split('/uploads/')[1] and unlink, no traversal check
#
# Find the secure block by looking for the userUploadDir line inside the startsWith block
# and replace the whole block with the vulnerable simple version.

# Mark the boundaries
start_marker = "if (file.filepath.startsWith(`/uploads/${req.user.id}`)) {"
secure_inner_marker = "const userUploadDir = path.join(uploads, req.user.id);"

if secure_inner_marker not in content:
    print("ERROR: secure block marker not found — already vulnerable?")
    # Check if already vulnerable
    if "split('/uploads/')[1]" in content:
        print("Already vulnerable — copying as-is")
        with open(src) as f:
            c = f.read()
        with open(dst, 'w') as f:
            f.write(c)
    sys.exit(0)

# Replace line by line
lines = content.split('\n')
out = []
i = 0
replaced = False
while i < len(lines):
    line = lines[i]
    # Detect start of the secure uploads block
    if (start_marker in line and
            i + 1 < len(lines) and
            "userUploadDir" in lines[i + 1]):
        # Emit vulnerable replacement
        indent = "  "
        out.append(line)  # keep the if (...) { line
        out.append(f"{indent}  const basePath = file.filepath.split('/uploads/')[1];")
        out.append(f"{indent}  const filepath = path.join(uploads, basePath);")
        out.append(f"{indent}  await fs.promises.unlink(filepath);")
        out.append(f"{indent}  return;")
        out.append(f"{indent}}}")
        replaced = True
        # Skip the original secure block body until the closing brace
        i += 1  # skip const userUploadDir line
        depth = 1  # we already emitted the opening {
        while i < len(lines):
            ch = lines[i]
            depth += ch.count('{') - ch.count('}')
            i += 1
            if depth <= 0:
                break
        continue  # do NOT increment i again
    else:
        out.append(line)
    i += 1

new_content = '\n'.join(out)
print(f"Replaced secure block: {replaced}")
print(f"path.relative in result: {'path.relative' in new_content} (expect False)")
print(f"split('/uploads/')[1] in result: {\"split('/uploads/')[1]\" in new_content} (expect True)")

with open(dst, 'w') as f:
    f.write(new_content)
print(f"Written to {dst}")
