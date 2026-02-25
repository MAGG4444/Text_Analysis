# 本地训练结构（TXT 即插即用）

这个目录提供一个简化版训练流程：
- 角色拆分（Character separation）
- 角色心理分析（Character psychology）
- 故事氛围分析（Story atmosphere）
- 可视化图表输出（Visual charts）

## 1. 目录约定

- `training/data/raw/train/`：训练语料（放 `.txt`）
- `training/data/raw/val/`：可选验证语料（放 `.txt`）
- `training/models/`：训练后的模型文件
- `training/outputs/`：分析结果与图表输出
- `training/scripts/train_models.py`：训练脚本
- `training/scripts/analyze_story.py`：单篇故事分析与画图脚本

## 2. 只需要做的事

### 第一步：放入训练文本

把你的故事文本直接放入：

- `training/data/raw/train/*.txt`

可选：把验证文本放入：

- `training/data/raw/val/*.txt`

支持子目录，脚本会递归读取所有 `.txt`。

### 第二步：训练

在项目根目录执行：

```bash
python training/scripts/train_models.py
```

训练完成后会生成：

- `training/models/psychology_model.joblib`
- `training/models/atmosphere_model.joblib`
- `training/models/character_catalog.json`
- `training/models/training_report.json`

### 第三步：分析任意一篇故事并出图

```bash
python training/scripts/analyze_story.py --input "你的故事.txt"
```

输出在 `training/outputs/`：

- `analysis_result.json`
- `atmosphere_timeline.png`
- `character_mentions_timeline.png`
- `character_psychology_distribution.png`

## 3. 这个版本的训练逻辑（简单版）

为了让你只用 TXT 就能跑，当前使用了“弱监督”方式：
- 自动切句、切场景
- 自动抽取角色名
- 通过词典规则生成心理/氛围的伪标签
- 再用文本分类器训练出本地模型

这让流程非常快、门槛低，但效果上限受语料质量影响较大。

## 4. 后续升级方向

如果你后续愿意标注小规模数据（例如 2000~5000 句），可以把准确率明显提高：
- 人工标注角色心理标签
- 人工标注场景氛围标签
- 使用同一结构替换为真实标签训练
