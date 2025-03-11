#### 对用户问题的处理

```python
words = query.split()

for word in words:
    # 如果包含有 @ 以及系统中的 agent 列表中存在
    # 则认为这是一个 agent 的指令，调用指定的 agent 进行处理
    if word.startswith('@'): and word[1:] in agents.keys():

        agent = agents[word.replace('@', '')]
    else:
        print(word, end="")
        pass
```

#### 添加用户的问题到 messages

```python
messages.append({"role": "user","content": query})
```

#### 允许定义的最大的对话轮次

```python
init_lens = len(messages)

while len(messages) - init_lens < MAX_TURNS:
```
