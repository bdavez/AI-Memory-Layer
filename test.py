sudo python3 - << 'EOF'
import backend.memory_summarizer as m
import inspect
print(inspect.getsourcefile(m))
EOF
