# 第八课：什么是 RAG？

## 8.1 一个场景

你是一个作家。你的小说已经写了 10 万字，分布在 15 个章节里。

突然，你想起在第三章里有一段关于「下雨」的精彩描写，你想找到它看看。但是你记不清是哪一节了。

你问 AI：「帮我找找我写过的关于下雨的段落。」

### 如果没有 RAG

AI 只能回答：

> 「让我猜一下……可能是第三章第二节？我记得那里有提到雨……但我不确定。」

因为 AI 的**记忆是有限的**——它的上下文窗口只能容纳几万 token。它不可能记住 10 万字小说的每一个细节。所以它只能靠「猜测」来回答，很可能给出错误的信息（这就是**幻觉**）。

### 如果有 RAG

AI 会这样做：

```
步骤 1：RAG 引擎扫描所有章节 → 切成 200 多个段落
步骤 2：对「关于下雨的段落」做语义搜索
步骤 3：找到 3 个相关段落：
   - 第三章第二节：「雨下了一整夜……」
   - 第七章第一节：「窗外又下起了雨……」
   - 第十二章第四节：「雨停了，阳光……」
步骤 4：把这三个段落注入 AI 的上下文
步骤 5：AI 基于真实内容回答

结果：AI 准确告诉你每段在哪一章、写了什么、怎么找到的。
```

## 8.2 RAG 是什么？

**RAG = Retrieval-Augmented Generation（检索增强生成）**

它的核心思想非常简单：

```
传统 AI：用户提问 → AI 凭记忆回答（可能编造）

RAG：    用户提问 → 从资料库检索相关文档 → 注入上下文 → AI 基于文档回答
                           ↑
                    多了一步「检索」
```

**RAG 的本质是：不给 AI 死记硬背的机会，让它每次都查资料再回答。**

## 8.3 RAG 的三个步骤

### 第一步：建索引（Indexing）

把所有的章节正文拆成小段落，然后给每个段落建立一个"关键词索引"。

```
原始数据：
  第一章：「主角站在雨中，看着孤儿院的大门……」
  第二章：「一位长者翻开书，阳光透过窗户……」
  
分块后：
  块 1：「主角站在雨中，看着孤儿院的大门……」  → 来自第一章
  块 2：「一位长者翻开书，阳光透过窗户……」        → 来自第二章
  ...

建立索引（TF-IDF）：
  "主角" → 出现在块 1
  "雨"   → 出现在块 1
  "一位长者" → 出现在块 2
  "阳光"   → 出现在块 2
  ...
```

这个索引就像书的**目录**——告诉你每个词出现在哪些段落里。

### 第二步：检索（Retrieval）

当用户提问时，RAG 引擎做两件事：

1. 把问题拆成关键词（比如「下雨的段落」→「下雨」「段落」）
2. 在索引中找这些关键词出现最多的段落

**关键词越匹配的段落，得分越高**，排在最前面返回。

### 第三步：生成（Generation）

把检索到的段落**注入 AI 的上下文**，让 AI 基于这些真实内容来回答：

```
你发给 API 的消息：

system: "你是一个写作助手。..."
user: "帮我找找关于下雨的段落"

# 注入 RAG 结果
user: "【参考内容】
  第三章第二节：雨下了一整夜，主角听着屋檐的水声睡不着。
  第七章第一节：窗外又下起了雨，一位长者放下了书。
  ...

请基于以上参考内容回答用户的问题。"
```

AI 看到这些参考内容后，就能给出准确答案了。

## 8.4 ReWrite 中的 RAG 实现

我们的 RAG 引擎实现在 `rag.py` 中，只有 200 多行代码。它使用**TF-IDF 算法**——一种经典的信息检索算法。

### TF-IDF 是什么？

TF-IDF 是两个概念的组合：

| 缩写 | 全称 | 中文 | 含义 |
|------|------|------|------|
| TF | Term Frequency | 词频 | 一个词在段落中出现的次数 |
| IDF | Inverse Document Frequency | 逆文档频率 | 一个词在所有段落中出现的稀有程度 |

**直觉理解：**

- **TF**：如果「雨」在一个段落里出现了 5 次，它很可能和雨有关 → 这个词重要
- **IDF**：如果「雨」只出现在 3 个段落中，而「的」出现在所有段落中 → 「雨」比「的」更有区分度 → 更重要

两者乘起来就是 TF-IDF 得分，它衡量一个词对一个段落的重要程度。

### 代码实现（简化版）

```python
import math
from collections import Counter

def compute_tfidf(paragraphs):
    """计算所有段落的 TF-IDF 向量。"""
    
    # 1. 把每段拆成单词列表
    tokenized = [tokenize(p) for p in paragraphs]
    
    # 2. 计算 IDF：每个词在多少段落中出现过
    n = len(paragraphs)
    df = {}  # document frequency
    for tokens in tokenized:
        for word in set(tokens):  # set 去重，一个段落只算一次
            df[word] = df.get(word, 0) + 1
    
    # 3. 计算 IDF 值
    idf = {}
    for word, count in df.items():
        idf[word] = math.log((n + 1) / (count + 1)) + 1
    
    # 4. 计算每段的 TF-IDF 向量
    vectors = []
    for tokens in tokenized:
        tf = Counter(tokens)
        max_tf = max(tf.values())
        vec = {}
        for word, freq in tf.items():
            tf_value = freq / max_tf  # 归一化词频
            vec[word] = tf_value * idf.get(word, 1)
        vectors.append(vec)
    
    return vectors, idf
```

### 搜索过程

```python
def search(query, vectors, idf, paragraphs):
    # 1. 把查询也转成 TF-IDF 向量
    query_tokens = tokenize(query)
    q_vec = {}
    for word in set(query_tokens):
        q_vec[word] = idf.get(word, 1)  # 查询向量
    
    # 2. 计算查询与每个段落的余弦相似度
    scores = []
    for i, vec in enumerate(vectors):
        # 计算两个向量的点积 / 长度乘积 = 余弦相似度
        score = cosine_similarity(q_vec, vec)
        scores.append((score, i))
    
    # 3. 按相似度排序，返回 TOP K
    scores.sort(reverse=True)
    return [paragraphs[i] for score, i in scores[:5]]
```

## 8.5 RAG vs Skill：什么时候用哪个？

RAG 和 Skill 是互补关系：

```
你明确知道要找什么 → Skill（精确查找）
你不知道具体在哪 → RAG（语义搜索）
```

| 场景 | 用哪个 | 为什么 |
|------|--------|--------|
| 「主角的年龄是多少？」 | Skill：get_characters | 知道要找"主角"这个角色 |
| 「边陲小镇在哪个国家？」 | Skill：get_map | 有明确的 parent_id 关系 |
| 「描写下雨的段落」 | RAG：search_chapters | 不知道在哪一章 |
| 「主角和一位长者第一次见面的场景」 | RAG：search_chapters | 记不清章节和细节 |
| 「把第一章标题改成序章」 | Skill：rename_chapter | 知道是第一章 |
| 「找出所有提到"自然之力"的地方」 | RAG：search_chapters | 可能分散在多个章节 |

**AI 会自动选择用哪个。** 如果它觉得需要搜索正文，就会调 `search_chapters`；如果觉得需要查结构化数据，就会调对应的 get Skill。

## 8.6 RAG 的局限性

RAG 不是万能的：

| 限制 | 说明 |
|------|------|
| **只搜索正文** | 目前只索引了章节 HTML，不搜人物卡/大纲等其他模块 |
| **关键词匹配** | 我们的实现用 TF-IDF（关键词匹配），不是真正的语义理解 |
| **段落级别** | 返回的是段落不是句子，可能不够精确 |
| **需要刷新索引** | 章节内容变化后需要重建索引（自动触发） |

如果要做到更好的语义理解，可以用**向量数据库**（如 Chroma） + **Embedding 模型**，但需要额外依赖。目前的 TF-IDF 实现零外部依赖，够用了。

## 8.7 小结

- **RAG** = 检索 + 生成 = 先查资料再回答
- 解决 AI **记忆有限**和**容易幻觉**的问题
- 步骤：建索引 → 检索 → 注入上下文 → 生成回答
- 我们用 **TF-IDF** 算法实现，零外部依赖
- RAG 和 Skill **互补**：Skill 管精确查询，RAG 管模糊搜索
- AI 自动选择用 Skill 还是 RAG

下一课我们把所有知识串起来，看完整代码架构。
