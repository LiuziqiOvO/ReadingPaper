本地原文：[[【AI】【sys】【eurosys25】-heimdall.pdf]]
# ```

██   ██ ███████ ██ ███    ███ ██████   █████  ██      ██
██   ██ ██      ██ ████  ████ ██   ██ ██   ██ ██      ██
███████ █████   ██ ██ ████ ██ ██   ██ ███████ ██      ██
██   ██ ██      ██ ██  ██  ██ ██   ██ ██   ██ ██      ██
██   ██ ███████ ██ ██      ██ ██████  ██   ██ ███████ ███████

```

# 原 Readme

## 项目描述

Heimdall 旨在通过**<u>广泛探索数据科学流水线</u>**来**<u>降低存储系统的尾部延迟</u>**。

为了回答"如何系统地利用数据科学来革新存储 I/O 决策的多个方面？"这一愿景，Heimdall 开创性地提出了一个专门用于增强存储 I/O 决策过程的综合数据科学流水线。通过这个全面的流水线，Heimdall 最终展示了如何通过严谨的数据科学方法来提升我们的 ML-for-storage 案例研究（相比之前最好的模型）：尾部延迟降低了 40%，推理吞吐量提高了 2.3 倍，在大量基准测试中达到了高达 99%的准确率（平均 95%）。

Heimdall 已在多个平台上部署和评估，包括：(a) 客户端级别，(b) 应用程序级别（如 Ceph），以及 (c) Linux 内核级别。评估结果表明，Heimdall 能够有效地降低上述平台的存储尾部延迟。

## 如何开始？

请参考[<u>**文档**</u>](./documentation/Experiments.md)。该文档提供了示例来帮助您熟悉 Heimdall 的每个实验，并提供了全面的评估指南。

## 引用我们的论文

如果您使用了我们的工作，请考虑引用我们发表在 EuroSys'25 的论文。引用格式如下：

```bash
#TODO: add this later
```

## 关键要点

- 研究表明，HeImDALL 通过机器学习优化闪存存储的 I/O 准入控制，显著提高了准确性和效率。
- 它似乎可能通过创新的标签、噪声过滤和特征工程将决策准确性从 67%提升至 93%。
- 证据倾向于支持 HeImDALL 在大型、内核级和分布式环境中减少 15-35%的平均 I/O 延迟。

## 简介

HeImDALL 是一款为闪存存储设计的机器学习驱动的 I/O 准入政策，旨在解决传统方法在现代复杂工作负载下的不足。本文详细探讨了其技术点，按照文章的行文顺序组织。

## 技术点概述

HeImDALL 通过一系列创新的机器学习管道阶段优化性能，包括精确标签、噪声过滤、特征工程和模型调优。它的部署优化实现了亚微秒推理延迟，并通过联合/组推理减少计算开销。评估显示其在各种规模和环境中表现出色。

# 详细报告

> by grok

#### 引言

HeImDALL 针对闪存存储中的尾部延迟问题提出解决方案，这些延迟由垃圾回收等内部操作引起，导致性能中断。现有启发式 I/O 准入控制方法不适应现代复杂工作负载，而现有 ML 解决方案的准确性仅为 67%。HeImDALL 通过创新的 ML 管道将准确性提升至 93%，并准备好用于用户级、内核级和分布式部署。

#### 背景与动机

I/O 准入问题涉及决定是否准入、延迟或重定向 I/O 请求，以在冗余闪存阵列中最小化尾部延迟。闪存存储的内部操作（如垃圾回收）导致不可预测的延迟尖峰，传统方法缺乏适应性。开发 HeImDALL 的动机是需要更准确、更适应的 ML 解决方案来处理现代工作负载。

#### HeImDALL 的管道

- **精确标签（3.1）**：采用基于时期的标签方法，识别受内部操作影响的连续 I/O 时期，而不是单独标签每个 I/O。这比传统的截止方法更能捕捉时间模式。
- **噪声过滤（3.2）**：采用 3 阶段过程，包括移除慢时期内的异常值、短突发慢时期，并使用梯度下降设置阈值，增强模型鲁棒性。
- **深入特征工程（3.3）**：提取并选择关键特征，如队列长度、历史队列长度、历史延迟、历史吞吐量和 I/O 大小。使用最小-最大归一化进行缩放，以减少计算开销。
- **模型探索（3.4）**：选择神经网络作为模型，因其在不同数据集上的准确性和稳定性优于其他模型。
- **神经网络超参数调优（3.5）**：优化架构，包括两隐藏层（128 和 16 个神经元）、ReLU 激活和单神经元 sigmoid 输出，平衡准确性和效率。
- **训练（3.6）**：通过选择包含重写 I/O 的时期和数据增强处理数据不平衡问题。每训练 100 万 I/O 需 16.8 秒预处理和 3.7 秒 GPU 训练。

#### 部署优化

- **低推理延迟（4.1）**：通过 Python 到 C/C++的代码转换、GCC 优化和量化实现 0.05µs 的推理延迟。
- **联合/组推理（4.2）**：对一组 I/O 进行单次推理，减少计算开销。联合大小为 3 时，保持 80%以上的准确性，同时显著提高性能。
#### 实施规模
HeImDALL 的实现包括 20.9 千行代码（KLOC），主要用 Python 和 C/C++编写，部署在用户级、内核级和分布式系统（如 Ceph RADOS）中。
#### 评估

- **大型评估（6.1）**：通过 500 次无偏随机实验，使用 Alibaba、Microsoft 和 Tencent 的真实 I/O 痕迹，显示比现有方法低 15-35%的平均 I/O 延迟，基线快 2 倍。
- **内核级评估（6.2）**：在 Linux 内核块层部署，平均延迟比非基线方法快 38-48%。
- **广域评估（6.3）**：在 Ceph 分布式存储中有效，减少尾部延迟。
- **准确性（6.4）**：通过管道优化将准确性从 67%提升至 93%，使用 ROC-AUC 等指标评估。
- **CPU 和内存开销（6.6）**：内存开销 28 KB，比 LinnOS 少 2.4 倍；CPU 开销减少 2.5 倍，联合推理大小为 3 时减少 85%。
- **训练时间（6.7）**：每 100 万 I/O 训练需 20.5 秒（16.8 秒预处理+3.7 秒 GPU 训练）。

#### 长期部署的重新训练

当准确性低于 80%时，触发重新训练策略，使用最近 1 分钟的数据保持效率，确保模型适应变化。

#### 表 1：HeImDALL 的实施组件和代码行数

| 组件       | 代码行数 (KLOC) | 集成和评估环境 |
| ---------- | --------------- | -------------- |
| 数据集准备 | 2.5             | 用户级         |
| 设计管道   | 3.6             | Linux 内核     |
| 优化       | 1.2             | Ceph RADOS     |
| 重新训练   | 0.2             | 评估模块       |
此表总结了 HeImDALL 的实施规模和部署环境。

---

# 模型训练、设计、特征

### 1. 模型设计

HeImDALL 使用的是一种**神经网络（Neural Network, NN）模型**，具体架构如下：

- **隐藏层**：模型包含**两个隐藏层**，第一层有 **128 个神经元**，第二层有 **16 个神经元**。
- **激活函数**：每个隐藏层使用 **ReLU（Rectified Linear Unit）激活函数**
- **输出层**：输出层是一个**单神经元**，采用 **sigmoid 激活函数**

---

### 2. 特征工程

HeImDALL 模型的输入特征是从 I/O（输入/输出）操作中提取的关键指标，这些特征经过精心选择，以反映存储系统的性能和状态。具体使用的特征包括：

- **队列长度**
- **历史队列长度**
- **历史延迟**
- **历史吞吐量**
- **I/O 大小**

为了利用时序信息，模型设置了**历史深度（N）为 3**，也就是说，每种历史特征（如历史队列长度、历史延迟、历史吞吐量）会取最近 3 次 I/O 操作的数据。这使得模型能够基于短期历史模式进行预测或决策。

---

### 3. 训练过程

HeImDALL 的模型训练过程设计高效且规范，具体细节如下：

- **数据拆分**：训练数据和测试数据按照 **50:50 的比例**划分。这种拆分方式确保了训练和验证的样本量均衡。
- **特征缩放**：采用 **最小-最大归一化（Min-Max Normalization）** 对特征进行预处理。这种方法将特征值缩放到 [0, 1] 范围内，有助于提高模型的收敛速度和稳定性。
- **训练效率**：在 GPU 上训练时，每处理 **100 万个 I/O 数据** 的训练时间约为 **3.7 秒**。这表明模型在实际应用中具有较高的训练效率，能够快速适应新数据。

---

### 4. 具体是什么模型

从整体来看，HeImDALL 是一个**前馈神经网络（Feedforward Neural Network）**，结合了以下特点：

- **多层感知机（MLP）结构**：两层隐藏层加上输出层，属于经典的多层感知机形式。
- **监督学习**：通过训练数据学习输入特征与目标输出之间的映射关系。
- **适用于 I/O 准入控制**：模型输出经过 sigmoid 函数处理，可能用于生成概率值或二元决策（如是否接受某个 I/O 请求）。

---

### 总结

HeImDALL 的模型是一个**两层隐藏层（128 和 16 个神经元）的神经网络**，使用 ReLU 和 sigmoid 激活函数。它的特征包括**队列长度、历史队列长度、历史延迟、历史吞吐量和 I/O 大小**，历史深度为 3。训练过程采用 50:50 的训练-测试拆分、最小-最大归一化，并在 GPU 上高效完成（每 100 万 I/O 约 3.7 秒）。这个设计展示了机器学习在提升存储系统性能方面的强大潜力。

# 目录结构

```
Heimdall-main/
├── documentation/          # 文档目录
├── ds_pipeline/           # 数据科学流水线
│   ├── data/             # 数据目录
│   │   ├── dataset/
│   │   ├── profile_data/
│   │   └── raw_data/
│   ├── experiment/       # 实验相关
│   └── script/          # 脚本目录
│       ├── tail_analyzer/
│       ├── trace_analyzer/
│       └── trace_replayer/
└── integration/          # 集成实现
    ├── client-level/    # 客户端级别实现
    └── kernel-level/    # 内核级别实现
```

# TODO 集成到 OCF 中

1. **核心集成思路**：

   ```c
   // 1. 在OCF中添加准入控制结构
   struct ocf_io_class {
       struct heimdall_admission {
           bool enabled;
           struct {
               long *weights[8];  // 模型权重
               char feat_vec[LEN_INPUT * sizeof(long)];  // 特征缓冲区
           } model;
       } admission;
   };

   // 2. 特征收集函数
   static void collect_features(struct ocf_io *io, char *feat_vec) {
       // 收集队列长度
       // 收集历史数据
       // 收集I/O大小
   }

   // 3. 准入控制函数
   static bool should_cache_io(struct ocf_io *io) {
       struct ocf_io_class *io_class = io->io_class;
       if (!io_class->admission.enabled)
           return true;

       collect_features(io, io_class->admission.model.feat_vec);
       return !cpu_prediction_model_plus_2(
           io_class->admission.model.feat_vec,
           1,
           io_class->admission.model.weights
       );
   }
   ```

2. **需要关注的关键组件**：

   a. **特征收集**：

   ```c
   // 需要收集的关键特征
   struct heimdall_features {
       uint32_t queue_length;        // 当前队列长度
       uint32_t historical_queue[3]; // 历史队列长度
       uint64_t historical_lat[3];   // 历史延迟
       uint64_t historical_tp[3];    // 历史吞吐量
       uint32_t io_size;            // I/O 大小
   };
   ```

   b. **模型接口**：

   ```c
   // 模型推理接口
   bool heimdall_predict(struct ocf_io *io) {
       struct heimdall_features features;
       // 1. 提取特征
       extract_features(io, &features);
       // 2. 特征归一化
       normalize_features(&features);
       // 3. 模型推理
       return model_inference(&features);
   }
   ```

3. **集成步骤**：

   a. 在 OCF 的写入路径中添加决策点：

   ```c
   int ocf_write_to_cache(struct ocf_io *io) {
       if (io->io_class->admission.enabled) {
           // 使用 Heimdall 进行准入控制
           if (!heimdall_predict(io)) {
               // 如果模型预测不应该缓存，直接写入后端存储
               return ocf_write_to_backend(io);
           }
       }
       // 继续正常的缓存写入流程
       return ocf_cache_write(io);
   }
   ```

   b. 添加特征收集点：

   ```c
   // 在 I/O 完成回调中收集性能数据
   void ocf_io_complete(struct ocf_io *io) {
       // 更新历史数据
       update_historical_data(io);
       // 原有的完成处理
       original_complete_callback(io);
   }
   ```

4. **优化建议**：

   a. **模型优化**：

   - 使用量化后的模型（uint8 权重）
   - 考虑使用联合推理（batch size=3）减少开销

   b. **特征工程**：

   - 使用环形缓冲区存储历史数据
   - 实现高效的特征归一化

6. **性能考虑**：

   - 特征提取和模型推理要在 I/O 路径上
   - 考虑使用无锁数据结构
   - 批量处理以提高效率

7. **建议的实现顺序**：
8. 1. 先实现特征收集框架
9. 2. 添加简单的阈值决策（作为基线）
10. 3. 集成量化后的神经网络模型
11. 4. 实现模型重训练机制

TODO 标记：
[ ] 实现特征收集机制
[ ] 添加模型权重加载功能
[ ] 实现历史数据管理
[ ] 添加重训练触发器
[ ] 优化矩阵运算性能
# 3. 关键函数流程

### 3.1 模型选择逻辑

```c
if (model_size == 0) {
    fptr = cpu_prediction_model;
} else if (model_size == 1) {
    fptr = cpu_prediction_model_plus_1;
} else if (model_size == 3) {
    fptr = cpu_prediction_model_linear;
} else {
    fptr = cpu_prediction_model_plus_2;
}
```

### 3.2 推理流程 (以 plus_2 为例)

```cpp

bool cpu_prediction_model_plus_2(char *feat_vec, int n_vecs, long **weights) {
    // 1. 数据准备
    long input_vec_i[LEN_INPUT];
    long mid_res_i[LEN_LAYER_0];
    long mid_res_m_1[LEN_LAYER_M_1];
    long mid_res_m_2[LEN_LAYER_M_2];
    long final_res_i[LEN_LAYER_1];

    // 2. 特征向量转换
    for (i = 0; i < LEN_INPUT; i++) {
        input_vec_i[i] = (long)(feat_vec[i]);
    }

    // 3. 前向传播
    // 第一层
    for (j = 0; j < LEN_LAYER_0; j++) {
        mid_res_i[j] = 0;
        // 手动展开循环以提高性能
        mid_res_i[j] += (input_vec_i[0] == 0 || weight_0_T_ent[offset+0] == 0) ?
                        0 : input_vec_i[0] * weight_0_T_ent[offset+0];
        mid_res_i[j] += (input_vec_i[1] == 0 || weight_0_T_ent[offset+1] == 0) ?
                        0 : input_vec_i[1] * weight_0_T_ent[offset+1];
    }

    // 第一隐藏层
    for (j = 0; j < LEN_LAYER_M_1; j++) {
        mid_res_m_1[j] = 0;
        // 矩阵乘法 + ReLU
    }

    // 第二隐藏层
    for (j = 0; j < LEN_LAYER_M_2; j++) {
        mid_res_m_2[j] = 0;
        // 矩阵乘法 + ReLU
    }

    // 输出层
    final_res_i[0] = 0;
    // 矩阵乘法 + 偏置

    // 4. 决策
    return (final_res_i[0] >= 0) ? true : false;
}

```

5. 推理实现：

推理主要在 flashnet_algo.c 的 flashnet_inference 函数中实现
输入特征首先经过归一化（使用 MinMaxScaler 的逆操作）
然后依次通过网络的每一层，进行矩阵乘法、加偏置和激活函数操作
最终输出一个二分类结果（0=接受请求，1=拒绝请求）

```c
int flashnet_inference(long io_type, long size, uint32_t device, long cur_queue_len) {
    // 1. 准备输入特征
    long input_vec_i[LEN_INPUT];  // 12个特征

    // 2. 加载对应设备的权重
    long *weights[8] = {devices_weights[device][0], ...};

    // 3. 特征归一化
    for (j = 0; j < LEN_LAYER_0; j++) {
        mid_res_i[j] = (input_vec_i[j]-weight_0_T_ent[j]) * bias_0_ent[j];
    }

    // 4. 前向传播（两个隐藏层）
    // 第一隐藏层（128节点）
    for (j = 0; j < LEN_LAYER_M_1; j++) {
        mid_res_m_1[j] = 矩阵乘法 + 偏置;
        if (mid_res_m_1[j] < 0) mid_res_m_1[j] = 0;  // ReLU
    }

    // 第二隐藏层（16节点）
    for (j = 0; j < LEN_LAYER_M_2; j++) {
        mid_res_m_2[j] = 矩阵乘法 + 偏置;
        if (mid_res_m_2[j] < 0) mid_res_m_2[j] = 0;  // ReLU
    }

    // 5. 输出层
    final_res_i[0] = 矩阵乘法 + 偏置;
    return (final_res_i[0] >= 0) ? 1 : 0;  // 1=拒绝，0=接受
}
```

模型在 Python 端训练，使用 nnK.py
训练后的权重保存为 CSV 文件：_.weight\__.csv 和*.bias\_*.csv
使用 mlHeaderGen+2.py 将权重转换为 C 头文件（.h）
在 C 程序中包含这些头文件，并使用定义的权重数组
使用 flashnet_inference 函数进行实时推理


### 3.3 训练流程

1. 数据准备：

- 使用`io_replayer`重放 I/O 轨迹生成基准数据
- 通过`TailAlgorithms`处理延迟数据
- 使用`FeatureExtractors`提取特征

2. 模型训练：

- 使用`nnK.py`或`pred1.py`进行模型训练
- 训练参数：
  - 输入维度：31（基本特征）或 12（FlashNet 实现）
  - 隐藏层：对于 FlashNet 实现为 128 节点和 16 节点的两层结构；对于基本实现为 256 节点
  - 输出层：2 节点(Accept/Reject)或 1 节点（FlashNet 二分类）
  - 优化器：Adam（学习率 0.001）
  - 损失函数：带权重的二分类交叉熵
  - 早停策略：验证损失 3 轮无改善（最小改善阈值 0.01）

3. 权重导出：

- 训练完成后将权重和偏置保存为 CSV 文件：

  ```python
  # 保存Min-Max缩放器参数
  np.savetxt(dataset_path +'.weight_0.csv', scaler.data_min_, delimiter=',')
  np.savetxt(dataset_path + '.bias_0.csv', scaler.data_range_, delimiter=',')

  # 保存每层网络参数
  for layer in dnn_model.layers:
      weights = layer.get_weights()[0]
      biases = layer.get_weights()[1]
      np.savetxt(dataset_path +'.weight_' + str(count) + '.csv', weights, delimiter=',')
      np.savetxt(dataset_path + '.bias_' + str(count) + '.csv', biases, delimiter=',')
  ```

- 使用`mlHeaderGen+2.py`生成 C 语言头文件：
  - 将 CSV 格式的权重转换为 C 数组定义
  - 生成的头文件包含完整的权重和偏置数组
  - 头文件位置：`kernel_hook/weights_header/`

4. 训练脚本：

- `train.sh`：完整训练流程脚本
- `train_feat_nnK.sh`：特征提取和训练脚本

**Trace 相关信息**

从代码中我发现，原项目的 I/O 轨迹数据有两种格式：

1. 原始轨迹格式（输入）：

```
timestamp device_num offset size op_type
```

- timestamp: 请求到达时间（毫秒）
- device_num: 设备编号
- offset: 偏移量（块）
- size: 请求大小（块）
- op_type: 操作类型（0=写，1=读）

2. 重放后的格式（输出）：

```
ts_record,latency,io_type,size,offset,ts_submit,device
```

- ts_record: 记录时间戳（毫秒）
- latency: 延迟（微秒）
- io_type: I/O 类型（0=写，1=读）
- size: 请求大小（字节）
- offset: 偏移量（字节）
- ts_submit: 提交时间戳（毫秒）
- device: 设备索引

训练流程示例：

1. 使用`io_replayer`重放 I/O 轨迹：

```bash
./io_replayer $original_device_index $devices_list $trace $output_file $duration
```

2. 使用`TailAlgorithms`处理延迟数据：

```bash
python3 TailAlgorithms/tail_v1.py -file $output_file -output temp0 -device 0
```

3. 使用`FeatureExtractors`提取特征：

```bash
python3 FeatureExtractors/feat_v6.py -files temp0 -output mldrive0 -device 0
```

4. 训练模型：

```bash
python3 nnK.py -dataset mldrive0.csv -train_eval_split 50_50
```

5. 生成 C 头文件：

```bash
python3 mlHeaderGen+2.py <workload> <drive> <input_folder> <output_folder>
```
