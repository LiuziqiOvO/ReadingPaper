

> 可以寻找有没有缓存优化的空间
> 可以寻找有没有适配FDP优化的可能性


论文原型：
https://www.vldb.org/pvldb/vol15/p3548-yan.pdf
文档：
https://milvus.io/docs/zh/architecture_overview.md


>以下调研报告由gemini生成
--- 

# 向量数据库存储优化报告：以 Milvus 为核心

### 执行摘要

本报告对向量数据库的存储优化策略进行了全面分析，并深入探讨了领先的开源向量数据库 Milvus。报告重点关注索引技术、缓存机制、SSD 适配以及分层存储等实用方面，旨在提高人工智能/机器学习工作负载的性能并降低运营成本。核心要点包括量化技术在内存优化中的关键作用、DISKANN 在大型数据集上 SSD 适配的战略性应用，以及持续监控和配置调优的重要性。

### 1. 向量数据库和 Milvus 简介
#### 1.1 向量数据库在人工智能/机器学习工作负载中的作用
向量数据库专门设计用于存储、管理和查询高维向量。这些向量是图像、文本或抽象概念等复杂数据的数值表示，能够捕捉数据的含义和上下文细微差别，从而使机器能够理解和进行数学运算 1。它们的核心能力在于执行闪电般的相似性搜索，通过识别与给定查询向量在语义上相似的项目，从而在“数字干草堆中寻找针”般地快速找到目标，而非仅仅依赖于精确的关键词匹配 1。
向量数据库是现代人工智能应用不可或缺的强大基石，其关键应用包括：

- 语义搜索： 通过理解术语的上下文和含义来增强传统关键词搜索 2。
- 相似性搜索： 在高维空间中寻找与查询项在数学上接近的项目 2。
- 推荐引擎： 通过识别相似的用户或项目来提高推荐的准确性和相关性 2。
- 检索增强生成 (RAG)： 对知识库进行索引，为大型语言模型 (LLM) 检索相关上下文，从而确保更准确和上下文相关的响应 1。
- 图像和视觉搜索： 实现通过图像搜索功能来查找视觉上相似的产品或设计 4。

Milvus 被认为是专为相似性搜索和人工智能工作负载而优化的开源向量数据库 5。它能够高效地管理和搜索大规模向量数据，使其成为人工智能、机器学习和数据科学领域开发人员的重要工具 5。Milvus 采用列式数据库系统设计，在数据访问模式方面具有优势。这种设计在查询执行期间仅读

取查询中涉及的特定字段，而非整个行，从而显著减少了数据访问量 7。

#### 1.2 Milvus 架构：以存储为中心视角

Milvus 从零开始构建为云原生系统，旨在充分利用公共云环境（例如 AWS、Azure、GCP）的灵活性和弹性 5。其架构将计算与存储分离，允许不同功能根据需求独立扩展 7。Milvus 组件是无状态的微服务，这简化了通过 Kubernetes 实现的水平扩展，并能够从故障中快速恢复，确保高可用性 7。

Milvus 架构明确将主要功能分离到不同的节点类型中，使其能够根据工作负载需求独立扩展：

- 查询节点 (Query Node)： 处理搜索查询并检索相关向量数据。它必须在内存中保存多个段的索引 5。
    
- 数据节点 (Data Node)： 处理数据摄取和存储，将新数据保存在“增长中的段”中 5。
    
- 索引节点 (Index Node)： 通过从存储层读取数据段来构建和管理向量索引（例如 IVF、HNSW），从而将计算密集型索引任务从查询节点和数据节点中分流 5。
    
- 根协调器 (Root Coordinator)： 作为中央控制平面，管理元数据、任务调度和节点协调 5。
    
- 代理 (Proxy)： 作为客户端应用程序的入口点，将请求路由到适当的查询或数据节点，并处理身份验证 5。
    

Milvus 架构中计算与存储的分离以及查询、数据和索引节点之间的明确职责划分，是其实现高效可扩展性的基础。这种解耦设计意味着，当某个功能（例如在高峰搜索期间的查询处理）需要扩展时，无需同步扩展其他功能（例如数据摄取或索引构建），从而避免了资源利用效率低下和成本增加的问题。通过这种方式，Milvus 能够根据其特定工作负载需求进行精细的资源分配，例如为对延迟敏感的搜索配置内存密集型查询节点，为高容量数据摄取优化磁盘 I/O 的数据节点，以及为计算密集型索引构建提供专用索引节点 7。这种设计直接带来了更好的资源分配、成本效益和性能隔离，这对于动态且通常波动的人工智能工作负载来说是一个显著优势。

Milvus 采用发布/订阅系统来实现大规模写入一致性。消息存储块对传入数据进行时间戳标记，然后查询节点和数据节点作为订阅者读取此发布日志。写入的扩展涉及扩展作为写入器的分片数量，数据的 ID 被哈希，哈希值决定了哪个分片将写入该数据 8。

Milvus 被描述为“云原生”并旨在利用公共云的灵活性 8。这种设计选择不仅仅是为了部署便利，更是与现代基础设施趋势的战略性对齐。云原生系统通过按需资源配置和自动化管理，本质上提供了弹性、弹性和成本效益。对于向量数据库而言，它们通常处理波动且计算密集型的人工智能/机器学习工作负载（例如用户查询的突然激增或大型批量摄取），这意味着系统可以动态适应负载变化，而无需人工干预或昂贵的硬件过度配置。这种设计使 Milvus 成为在公共云平台上构建人工智能应用程序的有力竞争者，从而实现更快的开发周期和更低的总拥有成本。

  

### 2. Milvus 数据存储基础
  

#### 2.1 向量数据、元数据和索引存储原理

  

向量的存储方式取决于所选择的索引策略，可以是原始数组形式，也可以是经过专门数据结构组织的形式 3。密集向量显式表示所有维度，而稀疏向量仅表示非零维度，从而为具有大量零的高维数据节省内存 3。

Milvus 中的每个数据点都包含一个向量以及其相关的特征和元数据，例如 ID、标签或描述 3。这些元数据与向量一起持久存储在存储层中 3。元数据的存储结构经过优化，旨在实现快速检索和低内存使用。可以采用压缩技术来最小化此相关数据的存储大小 3。

Milvus 的一个显著优势是它能够将向量相似性搜索与传统元数据过滤相结合 3。这意味着查询可以通过在向量搜索的同时应用过滤器（例如，“类别 = 服装”）来细化，从而实现更精细的结果 3。

在处理高维向量空间时，相似性搜索可能由于“维度诅咒”而计算成本高昂 10。如果查询包含元数据过滤器（例如，“查找

狗的相似图像，且是金毛寻回犬”），在执行向量相似性搜索之前应用这些过滤器，能够显著减少近似最近邻 (ANN) 算法需要处理的数据集大小。这种预过滤（或后过滤，取决于具体实现）充当粗粒度过滤器，极大地减少了需要进行更昂贵向量搜索的数据量 8。这直接转化为更快的查询响应时间和更低的计算负载，使整个系统更高效和可扩展，特别是对于复杂的、多条件搜索而言。

  

#### 2.2 数据的生命周期：增长中的段和已密封的段

  

Milvus 在内部将数据组织成“段”，这些段是预定义大小的数据块（默认为 512MB，但可配置为 1GB 或 2GB）8。这种基于段的方法对于效率和水平扩展至关重要 8。

当新数据摄取到 Milvus 中时，它最初会累积在“增长中的段”中 8。这些段驻留在查询节点和数据节点的内存中，保存尚未达到其预定义大小限制的数据 8。一旦增长中的段达到其容量（由

maxSize * sealProportion 决定），它就会被“密封” 12。已密封的段随后会从数据节点和查询节点刷新到持久存储层。此刷新过程是自动进行的，通常每 10 分钟一次 8。

当一个段被密封并刷新到持久存储后，索引节点会收到通知 8。然后，索引节点直接从存储层读取此已密封的数据段，专门为该段构建一个向量索引 8。由于索引是针对这些独立段单独构建的，因此它们可以并行搜索。这通过将工作负载分布到多个节点，显著减少了大量数据的搜索时间 8。

dataCoord.segment.maxSize 参数对于性能调优至关重要 12。通常，更大的段大小会导致更少的总段数，这可以通过减少跨许多小段进行索引和搜索的开销来提高查询性能 11。对于大规模部署，2GB 的段通常能在内存效率和查询速度之间提供最佳平衡，尤其是在查询节点具有 >16GB 内存的情况下 11。

这突出了 Milvus 中一个关键的性能调优旋钮。趋势是为大型部署配置更大的段，以获得更好的整体性能，特别是当查询节点配置了充足的内存时。其根本原因是，无论大小如何，每个段都会产生一些固定的管理、索引和搜索开销。通过将数据整合到更大的块中，这种固定开销分摊到更多数据上，从而实现更高效的资源利用（管理更少的元数据，减少跨段的索引查找）并最终加快查询处理。然而，需要注意的是潜在的权衡：如果数据更新非常频繁且需要立即搜索，更大的段可能意味着新数据被索引和刷新所需的时间稍长，或者在更新时需要重新索引更大的数据块。这强化了“可调权衡”的理念。

过于频繁地刷新段可能会导致生成大量小的已密封段。这会增加压缩开销（将小段合并为更大、更高效的段的过程），并可能对查询性能产生负面影响。Milvus 的自动密封和刷新机制旨在缓解此问题 12。

  

#### 2.3 持久化存储选项：对象存储和本地磁盘


Milvus 的存储层具有灵活性，支持各种持久化存储后端，包括本地 SSD、HDFS 等分布式文件系统，或 Amazon S3 和 Google Cloud Storage (GCS) 等云对象存储服务 5。对象存储主要用于持久化原始向量数据和相关元数据，为大型数据集提供持久性和可扩展性 13。

Milvus 2.6 引入了其新的预写日志 (WAL) 系统 Woodpecker，这是一项重要的架构演进。这种“无盘架构”（指消除了外部消息队列）旨在通过移除对 Kafka 或 Pulsar 等外部消息代理的依赖，从根本上提高写入性能并降低基础设施成本 14。基准测试显示，Woodpecker 在数据摄取方面实现了显著更高的吞吐量（例如，本地文件系统为 450 MB/s，S3 模式为 750 MB/s）和更低的延迟（例如，本地文件系统为 1.8 ms），优于 Kafka 15。这消除了管理独立消息队列集群的需求，从而简化了部署和操作开销 14。

转向 Woodpecker WAL 是 Milvus 针对写入密集型工作负载直接且有效的优化。通过将 WAL 机制内部化并消除对外部消息队列的依赖，Milvus 降低了架构复杂性，消除了网络跳数，并简化了数据摄取路径。这里的“无盘架构”可能指的是其高效地在内存中缓冲写入并优化其最终刷新到持久对象存储的能力，从而最大限度地减少外部队列可能需要的针对瞬态日志数据对本地磁盘的直接、频繁写入。这带来了更高的摄取吞吐量和更低的延迟，这对于持续更新其向量嵌入的实时人工智能应用程序至关重要。此外，消除外部组件直接转化为“经济节省”和“运营效率”14，通过减少受管服务的数量及其相关基础设施成本，使 Milvus 对成本敏感的部署更具吸引力。

对象存储的关键配置参数包括：

- minio.address / minio.port：指定对象存储服务的端点 12。
- minio.bucketName：分配独立的存储桶或逻辑前缀以避免数据冲突，特别是在多集群环境中 12。
- minio.rootPath：启用桶内命名空间以进一步隔离数据 12。
- minio.cloudProvider：标识正在使用的特定对象存储服务 (OSS) 后端（例如 AWS S3、GCS）12。

### 3. 存储优化战略性索引

#### 3.1 向量索引类型概述（HNSW、IVF、FLAT）及其存储影响

向量索引是一种数据结构，通过其向量表示优化相似数据点的搜索 10。它显著提高了相似性搜索的速度，同时对搜索准确性的影响最小 10。向量数据库采用各种技术来组织数据并最小化搜索空间：

- 基于树的索引： 分层组织向量（例如 k-d 树、Ball 树）10。
- 基于哈希的索引： 为相似向量生成哈希值（例如局部敏感哈希 (LSH)、二进制哈希）10。
- 基于图的索引： 构建互连节点的网络（例如可导航小世界 (NSW)、分层可导航小世界 (HNSW)）10。
- 基于量化的索引： 通过使用聚类中心近似向量来降低向量维度 10。
- 倒排文件 (IVF) 索引： 将向量分区到聚类中 10。
    

Milvus 支持多种索引类型，每种索引类型都具有独特的存储和性能影响：

- FLAT（穷举搜索/暴力搜索）：
- 机制： 不进行任何压缩或附加结构地存储向量。它对查询向量与数据集中所有向量进行穷举的暴力比较 11。
- 存储： 计算直接：向量数量 × 维度 × 4 字节（对于浮点向量）。开销最小 18。
- 权衡： 提供 100% 的召回率（完美准确性），但随着数据大小线性扩展，对于非常大的数据集而言，计算上不切实际且内存密集 11。
- IVF（倒排文件）：
- 机制： 使用 k-means 等算法将向量分区到聚类中。每个聚类都有一个质心。在索引期间，向量按其最近的质心分组。在查询期间，系统识别最近的质心并仅在这些聚类中搜索，从而大大减少计算量 18。
- 存储： 包括聚类质心的存储（聚类数量 × 维度 × 4 字节）和倒排列表（大约 向量数量 × 4 字节 用于聚类 ID）18。
- 权衡： 通过减少搜索空间，非常适合大型数据集，但需要预训练来定义聚类。准确性取决于聚类质量。比基于图的索引更节省内存 17。

- HNSW（分层可导航小世界）：
- 机制： 构建分层图，其中每一层都是前一层的子集（顶层稀疏，下层更密集）。搜索从顶层开始，导航到附近的节点，然后在下层细化路径 10。
- 存储： 在查询速度和召回率方面表现出色，但由于图存储而使用更多内存。大小与向量数量和向量之间的连接数量成正比（例如，100 万个向量，每个有 32 条边，将额外增加约 128MB 的基础存储）。由于图结构，通常具有更高的内存占用（原始向量数据的 2-3 倍）11。
- 权衡： 提供出色的查询速度和高召回率。作为内存索引，当数据库实例重新启动时必须重建，尽管 Milvus 具有重新加载机制 25。
- GPU 加速索引： Milvus 支持基于 GPU 的索引和查询执行，以实现高速向量计算，包括 GPU_CAGRA、GPU_BRUTE_FORCE、GPU_IVF_FLAT 和 GPU_IVF_PQ。这些索引在内存使用、精度和性能之间提供了不同的权衡 5。
    

索引类型的选择是一个基本且重要的存储优化决策。它直接影响内存占用、磁盘 I/O 模式、查询速度和搜索准确性等方面的具体行为。例如，HNSW 的高内存使用量 17 是其卓越查询速度和召回率的

先决条件，因为它将整个图结构保存在快速 RAM 中 20。相反，IVF 的分区策略通过将搜索范围限制在相关聚类中来

减少计算量 20，使其更节省磁盘空间，但可能不如 HNSW 准确。理解这些固有的权衡对于架构师选择符合其特定工作负载需求（例如，极低延迟与成本敏感、大规模与小规模、高召回率与可接受的近似值）的索引至关重要。“维度诅咒”10 进一步加剧了这些挑战，使得高效索引对于任何向量数据库都至关重要。

  

#### 3.2 向量量化（PQ、BQ、SQ）：减少占用空间和性能权衡
向量量化 (VQ) 是一种数据压缩技术，用于减小高维数据的大小 27。其主要目标是最小化内存使用并加速搜索操作，这对于将原始向量存储在快速内存中成本过高的大型数据集尤其重要 27。VQ 的工作原理是将高维向量转换为更小、更紧凑的表示形式，通常通过将值映射到较低精度数字（例如，32 位浮点数到 8 位整数）或通过使用码本中的质心表示子向量 27。

向量数据库中量化类型：

- 标量量化 (SQ)：
- 存储减少： 将每个 float32 维度（4 字节）转换为 int8（1 字节），实现 75% 的内存减少 27。
- 影响： 旨在实现最小的精度损失。由于使用 int8 值进行距离计算更简单，因此可以提供高达 2 倍的速度提升 27。
- 二进制量化 (BQ)：
- 存储减少： 将高维向量转换为简单的二进制（0 或 1）表示。对于 1536 维向量，这可以将内存从 6KB 减少到 192 字节，实现 32 倍的内存减少 27。
- 影响： 通过使用高度优化的 CPU 指令（XOR、Popcount）进行距离计算，提供最显著的处理速度增益（高达 40 倍）。然而，它是一种有损压缩技术，意味着它会省略大量信息，可能导致更大的精度损失。建议与至少 1024 维的模型一起使用，以最小化此损失 27。
- 乘积量化 (PQ)：
- 存储减少： 将高维向量分割成更小的子向量。然后，每个子向量映射到“码本”中的一个质心，原始向量由这些质心 ID 的序列表示。在某些配置中，这可以实现高达 64 倍的压缩 20。
- 影响： 大幅减少内存需求。通常与 IVF（IVF-PQ）结合使用，以首先缩小搜索空间。PQ 涉及召回率、性能和内存使用之间的权衡；高压缩可能导致质量显著下降（准确率约为 0.7）和索引速度变慢 20。

量化技术（SQ、BQ、PQ）明确地减小了向量大小 27。这种减小直接影响内存使用和存储占用 27。更低的内存使用允许更多向量驻留在更快的内存（RAM/SSD）中，这反过来又导致更快的搜索操作 27。这里的核心因果关系是：

压缩导致资源消耗减少，从而实现更高的性能和更低的成本。通过使向量更小，量化允许更大容量的数据适应昂贵、快速的内存（RAM）或更快的磁盘层（SSD），从而显著减少搜索过程中对较慢磁盘 I/O 的需求。这对于扩展到“十亿级”数据集至关重要，因为原始向量存储的成本将高得令人望而却步 20。固有的权衡是准确性（因为量化是一种有损压缩方法）20，但过采样和重新评分等复杂技术 27 旨在缓解此问题，从而在成本、速度和精度之间实现可调的平衡，这对于实际的人工智能应用程序至关重要。

表：向量量化比较

  

|            |           |                           |                 |                              |
| ---------- | --------- | ------------------------- | --------------- | ---------------------------- |
| 量化类型       | 存储减少因子    | 典型准确性影响                   | 典型性能影响（加速）      | 用例/考虑事项                      |
| 标量量化 (SQ)  | 75% 内存减少  | 最小损失                      | 高达 2 倍          | 默认选择；计算更简单                   |
| 二进制量化 (BQ) | 32 倍内存减少  | 显著损失，但某些模型可接受 (约 0.95 召回) | 高达 40 倍         | 适用于高维模型 (≥1024D)；使用优化 CPU 指令 |
| 乘积量化 (PQ)  | 高达 64 倍压缩 | 明显下降 (约 0.7 召回)           | 0.5 倍相对速度（索引较慢） | 内存关键系统；常与 IVF 结合             |
|            |           |                           |                 |                              |

为了抵消量化固有的精度损失，可以采用以下技术：

- 过采样： 在初始搜索中检索比所需最终限制更多的候选对象 27。
    
- 使用原始向量重新评分： 使用其原始未压缩向量重新评估过采样的候选对象，以获得更高的准确性。由于只处理一小部分向量，因此速度更快 27。
    
- 重新排序： 根据重新评分结果重新排序最终的 Top-K 候选对象 27。
    

Milvus 明确支持应用量化的索引类型，例如 IVF_SQ8、HNSW_PQ、HNSW_SQ 和 HNSW_PRQ 11。这些索引显著减小了索引大小和内存占用，使其成为精度不如规模或预算重要的工作负载的理想选择 11。

一些系统（例如 Qdrant）允许将原始向量存储在磁盘上，而仅将压缩的量化向量保留在 RAM 中 27。这显著降低了 RAM 使用率和成本，尽管如果磁盘延迟较高，可能需要禁用重新评分以保持速度 27。

在多个研究片段中，讨论索引和量化时反复提及“权衡”（速度与准确性、内存与召回率、成本与性能）的概念 17。Milvus 本身的设计目标就是“在性能和一致性之间进行可调的权衡”8。这不仅仅是一个技术细节，更是现代向量数据库（如 Milvus）的总体设计理念。与通常优先考虑严格 ACID 属性（原子性、一致性、隔离性、持久性）的传统数据库不同，向量数据库承认人工智能/机器学习应用程序通常具有灵活的需求。用户通常愿意接受搜索准确性上的轻微下降（例如，召回率为 0.95 而非 1.0），以换取查询速度、内存效率或成本降低方面的显著收益。这种“可调权衡”能力使开发人员和架构师能够精确地根据其应用程序的特定需求和预算限制来微调其部署，而不是被迫采用一刀切的解决方案。这种灵活性是关键的差异化因素，也是此类数据库在快速发展的人工智能/机器学习领域中广泛采用和流行的主要原因。

  

#### 3.3 Milvus 的 DISKANN 索引：弥合内存与 SSD 之间的鸿沟，适用于大型数据集

  

DISKANN 是一种混合磁盘/内存索引，专门设计用于处理超出可用 RAM 的海量数据集 11。它通过利用 SSD 存储大部分索引，同时保持高搜索准确性和速度，为纯内存索引提供了一种经济高效的替代方案 11。

DISKANN 通过在内存中保留索引的压缩部分（用于快速近似计算），同时将其余部分（全精度向量和 Vamana 图结构）驻留在磁盘上，从而平衡内存使用和性能 11。

主要组成部分：

- Vamana 图（基于磁盘）： 这是核心图结构，与全精度向量嵌入一起存储在 SSD 上 29。它通过优化过程构建，包括：
    

- 初始随机连接： 每个向量表示图中的一个节点，最初随机连接（例如，500 条边）以实现广泛连接 30。
    
- 修剪冗余边： 根据节点之间的距离丢弃不必要的连接，优先选择更高质量的边。max_degree 参数限制了每个节点的最大边数；更高的 max_degree 意味着更密集的图，可能带来更高的召回率，但也会增加内存使用和搜索时间 30。
    
- 添加战略性快捷方式： 引入长距离边以连接相距较远的数据点，使搜索能够快速跳过图，绕过中间节点并显著加快导航 30。  
    search_list_size 参数决定了此细化过程的广度 30。
    

- 乘积量化 (PQ)（内存压缩）： DISKANN 使用 PQ 将高维向量压缩成更小的 PQ 码。这些压缩码存储在 RAM 中，用于快速近似距离计算，为减少下次访问 SSD 的邻居节点数量提供指导 29。
    

- pq_code_budget_gb_ratio：此参数管理存储 PQ 码的内存占用，允许在搜索准确性和内存资源之间进行权衡 30。
    

搜索过程：

- 提供一个查询向量，DISKANN 从 Vamana 图中的一个入口点开始（通常靠近全局质心）29。
    
- 它使用内存中的 PQ 码探索候选邻居以进行近似距离计算 29。
    
- 然后选择一部分有希望的邻居，使用其原始未压缩向量进行精确距离评估，这需要从磁盘读取数据 30。
    
- beam_width_ratio：控制搜索的广度，决定并行选择多少候选邻居来探索其邻居。更大的比率会导致更广泛的探索，可能带来更高的准确性，但会增加计算成本和磁盘 I/O 30。
    
- search_cache_budget_gb_ratio：控制分配用于缓存频繁访问的磁盘数据的内存比例，最大限度地减少重复搜索的磁盘 I/O 30。
    

在 Milvus 中启用 DISKANN：

- 默认情况下，Milvus 中禁用 DISKANN，以优先考虑适用于 RAM 的数据集的内存索引速度 30。
    
- 要启用，请找到 milvus.yaml 配置文件并将 queryNode.enableDisk 设置为 true 30。
    

优化 DISKANN 的存储：

- 为了获得最佳性能，强烈建议将 Milvus 数据（特别是数据目录）存储在快速 NVMe SSD 上 30。
    
- Milvus Standalone： 将 Milvus 数据目录挂载到 Docker 容器内的 NVMe SSD 上（例如，通过更新 docker-compose.yml 文件中的 volumes 部分）30。
    
- Milvus Cluster： 通过容器编排设置，将 Milvus 数据目录挂载到查询节点和索引节点容器中的 NVMe SSD 上。这可确保搜索和索引操作的快速读写速度 30。
    

DISKANN 的混合方法是其能够以低于纯内存解决方案的成本扩展到“十亿级”数据集的直接原因。通过将大部分索引（Vamana 图结构和全精度向量）卸载到 SSD，它显著减少了昂贵的 RAM 占用 29。内存中的 PQ 码提供了一个快速近似层，作为“指导”，以最大限度地减少精确距离计算所需的较慢磁盘读取次数 29。这种设计允许组织处理海量数据集，而无需承担与配置大量 RAM 相关的过高硬件成本 31。权衡是查询延迟略高于纯内存索引（DISKANN 通常约为 100 毫秒，而 HNSW 为微秒级）11，但对于许多大规模应用程序而言，这是为了显著节省成本和提高容量而可接受且必要的折衷。

DISKANN 参数可以通过 milvus.yaml 配置文件或在索引创建或搜索操作期间使用 Milvus SDK 动态微调 30。

  

### 4. 提升查询性能的缓存机制

  
  

#### 4.1 缓存对向量搜索的重要性

  

缓存是一种通过将频繁访问的数据存储在更快、临时存储（如 RAM 或本地磁盘）中来减少延迟并减轻后端系统负载的基本策略 2。其核心在于最大限度地减少磁盘 I/O，这是数据库系统中的常见瓶颈 34。通过从缓存中提供重复请求，系统避免了重复从较慢的基于磁盘的存储中获取数据 34。

对于计算密集型（特别是对于大型数据集和复杂模型）的向量搜索而言，缓存充当了捷径。它通过存储预计算结果或频繁访问的数据在内存中，避免了冗余计算（例如，重新生成嵌入、重新运行相似性搜索）33。缓存使系统能够更快地响应请求并处理更高的流量负载，从而使系统更具响应性和可扩展性，特别是对于频繁或相似的查询 33。它特别有利于个性化推荐、人工智能驱动的搜索引擎、聊天机器人和欺诈检测等应用，在这些应用中，快速响应和高效资源利用至关重要 35。

缓存作为一种普遍适用且基础的性能优化策略，不仅适用于向量数据库，也适用于任何数据密集型系统。其基本原理是相同的：利用数据访问的局部性和时空模式，从更快、更近的存储层提供请求。对于向量数据库而言，相似性搜索是计算密集型的，并且通常涉及遍历复杂的索引结构，缓存频繁访问的向量、索引段甚至查询结果 32 可以显著改善用户体验并减少主存储和计算资源的负载。这强化了缓存是整个存储层次结构中的关键层，弥合了快速 CPU/RAM 与较慢磁盘/对象存储之间的差距，并且是许多人工智能应用实现实时性能的先决条件。

  

#### 4.2 Milvus 的分块缓存和查询节点缓存策略

  

Milvus 专门实现了“分块缓存”机制，用于在查询节点上预加载对象存储中的数据到本地硬盘（通常是 SSD）中，在实际需要查询之前 37。这种预加载显著提高了向量检索性能，通过减少将数据从较慢的对象存储加载到较快的内存缓存所需的时间 37。当收到查询请求时，Milvus 的 Segcore（查询引擎）首先检查此本地磁盘缓存。如果数据存在于缓存中，则可以快速检索，绕过对象存储 37。

queryNode.cache.warmup 参数控制分块缓存预加载的行为：

- async（默认）：Milvus 在后台异步预加载数据。这不会影响初始集合加载时间，但可能导致加载完成后立即进行向量检索时出现短暂延迟，因为数据仍在预热中 37。
    
- sync：Milvus 同步预加载数据。这可能会增加初始集合加载时间，但用户可以在加载过程完成后立即执行查询，而不会有任何延迟 37。
    
- disable：Milvus 不将数据预加载到本地磁盘缓存中 37。
    

分块缓存充当对象存储（提供持久性和可扩展性）与驻留在 RAM 中的快速内存索引之间的一个中间、更快的缓冲区。对象存储通常比本地磁盘（尤其是 SSD）具有更高的延迟。通过将频繁访问的数据段预加载到查询节点上的本地 SSD，Milvus 有效地减少了查询的“冷启动”延迟，这些查询命中了尚未完全驻留在 RAM 中的数据。这意味着即使数据不在 RAM 中，它也位于 更快的本地磁盘 (SSD) 上，而不是远程对象存储，从而显著减少了查询响应时间，特别是在集合加载后或节点重启后的初始查询。这突出了 Milvus 内部的一种实用分层缓存方法，优化了从冷存储到热内存的数据路径。

查询节点被设计为拥有足够的内存来容纳多个段的内存索引 8。这种内存缓存对于低延迟查询响应至关重要 8。为了确定分块缓存是否正常工作，建议检查加载集合后搜索/查询请求的延迟。对象存储上的高吞吐量也表明分块缓存正在积极工作 37。

  

#### 4.3 语义缓存和应用程序级缓存考量

  

语义缓存是一种专门的缓存机制，旨在通过重用先前执行查询的结果来加速相似性搜索查询，即使它们的输入向量略有不同 35。与依赖精确匹配的传统缓存不同，语义缓存识别查询之间的概念相似性 35。

其工作原理是识别相似性而非依赖精确匹配 35。当发出新查询时，Qdrant（一个具有此功能的向量数据库示例）使用基于距离的指标（余弦相似度、欧几里得距离）检查是否已缓存了语义相似的查询 35。如果在可配置的相似性阈值内找到匹配项，则检索缓存结果，从而节省计算资源 35。

语义缓存的优势包括性能提升、成本效益、可扩展性改进和“更智能的缓存”，非常适合人工智能驱动的应用程序，在这些应用程序中，查询可能不完全相同，但在概念上足够相似以重用结果（例如，个性化推荐、聊天机器人）35。语义缓存采用智能失效机制，以确保过时或不相关的条目定期被移除 35。

传统缓存依赖于请求的精确匹配 32。而以 Qdrant 为例的语义缓存，通过理解查询之间的

概念相似性，即使它们的输入向量略有不同，也超越了这一点 35。这是缓存策略的一个明显演进。在向量搜索的背景下，查询通常是自然语言或图像，由于用户输入的固有可变性和细微差别，精确的查询匹配对于缓存通常是不够的。语义缓存通过利用向量嵌入本身来解决这一限制：如果两个查询，即使措辞不同，也产生非常相似的嵌入（即，语义上接近），则可以重用它们的结果。这是一个强大的新兴主题，因为它允许在人工智能驱动的应用程序中实现更高的缓存命中率，显著提高性能并减少向量数据库和任何上游 LLM（在 RAG 场景中）的计算负载 35。它代表了一种更智能、更自适应的缓存策略，专门为人工智能工作负载的细微差别和复杂性量身定制，超越了简单的键值查找，达到了概念理解的层面。

应用程序级缓存：开发人员可以使用 Redis 或 Memcached 等工具，通过应用程序层缓存来补充 Milvus 的内置缓存，以处理频繁访问的读密集型数据 32。

- RAG 系统： 在 RAG 中，缓存可以存储查询/文档嵌入（以避免重新生成它们）、检索到的结果（用于频繁查询），甚至最终生成的响应（用于相同、稳定的答案）36。
    
- 语义搜索： 对于语义搜索，方法是设置一个向量缓存（例如，使用 Redis 或 FAISS）来存储嵌入及其相关的搜索结果。当新查询到达时，生成其嵌入，与缓存的嵌入进行比较，如果存在相似匹配（高于相似性阈值），则返回预计算结果 39。
    
- 缓存键设计： 精心设计缓存键对于平衡唯一性和冲突风险至关重要，通常通过对标准化输入数据和模型版本元数据的哈希组合来完成 40。
    
- 失效策略： 需要仔细实施失效策略（例如，基于时间的过期 (TTL)、事件驱动更新），以平衡性能提升与数据新鲜度 32。
    

  

#### 4.4 Milvus 缓存配置和优化

  

Milvus 的查询节点包含一个专用的缓存层，为频繁访问的数据和索引提供内存缓存，直接有助于降低读密集型工作负载的查询延迟 5。

为了优化缓存性能并解决缓存未命中问题，建议采取以下步骤：

- 分析缓存使用情况： 利用监控工具和日志来了解当前缓存使用模式并识别缓存未命中的位置 6。
    
- 优化缓存设置： 调整 Milvus 配置中的缓存大小和逐出策略，以优先处理频繁访问的数据 6。
    
- 增加缓存大小： 如果分析显示缓存大小不足，请考虑增加其大小以容纳更多数据，从而减少缓存未命中 6。
    
- 持续监控： 实施持续监控（例如，使用 Grafana）以实时跟踪缓存性能指标并进行迭代调整 6。
    

内存映射 I/O (queryNode.mmap)： 此参数允许 Milvus 切换标量字段和段加载的内存映射 I/O 12。

- 优点： 启用 mmap 可以通过将大量数据卸载到虚拟内存来显著减少驻留 RAM 使用量。这是一种实现极端内存节省的策略 12。
    
- 注意事项： 然而，如果底层磁盘 I/O 成为瓶颈，mmap 可能会降低延迟。如果标量过滤是工作负载的主要部分，在 I/O 受限的环境中，建议禁用 vectorIndex 和 scalarIndex 的 mmap 12。
    
- 磁盘使用： 当使用 mmap 构建 HNSW 索引时，由于索引开销和缓存，磁盘上的总数据大小可能会膨胀多达 1.8 倍。因此，预留额外的存储空间至关重要，特别是如果原始向量也在本地缓存 12。
    

queryNode.mmap 启用内存映射 I/O 12。这被明确指出可以“通过将大量数据卸载到虚拟内存来减少内存占用，从而显著减少驻留 RAM 使用量”12。然而，它也“可能在磁盘 I/O 成为瓶颈时降低延迟”12。

mmap 是一种强大的操作系统功能，Milvus 利用它来管理可能无法完全适应物理 RAM 的大型索引。它的主要好处是节省昂贵的 RAM 成本。然而，其因果关系在于，这种内存优化是以增加对底层磁盘子系统的依赖为代价的。如果磁盘（即使是快速 SSD）无法跟上 mmap 访问产生的随机 I/O 模式，性能将受到影响，因为系统将等待磁盘读取。这对于 SSD 尤其相关，因为 SSD 上的随机 I/O 可能不如顺序 I/O 高效，并会导致写入放大 41。因此，虽然

mmap 节省了 RAM，但它有效地将性能瓶颈转移到磁盘 I/O，因此需要快速 SSD（如 NVMe）并仔细监控磁盘性能，以确保它不会成为新的瓶颈。

对于利用 GPU 索引的 Milvus 部署，全局图形内存池用于 GPU 内存分配 26。此内存池可通过

gpu.initMemSize（初始大小）和 gpu.maxMemSize（最大限制）进行配置 26。从 Milvus 2.4.1 版本开始，此内存池主要用于搜索期间的临时 GPU 数据 26。

  

### 结论与建议

  

本报告深入探讨了向量数据库，特别是 Milvus 在存储优化方面的关键策略。核心发现表明，通过精细管理数据存储、利用先进的索引技术和实施智能缓存机制，可以显著提升 Milvus 的性能、可扩展性并降低运营成本。

以下是具体的结论和建议：

1. 架构解耦是性能和成本效益的基础： Milvus 的云原生分布式架构，通过将计算与存储分离，并独立扩展查询、数据和索引节点，实现了资源利用的最大化。这种设计允许系统根据实时工作负载需求进行弹性伸缩，避免了不必要的资源浪费。
    

- 建议： 在部署 Milvus 时，应充分利用其组件解耦的优势，根据实际的读写比例和索引需求，独立配置和扩展不同类型的节点。
    

2. 段管理是性能调优的关键杠杆： Milvus 将数据组织成段，并区分增长中的段和已密封的段。段的大小直接影响查询性能和索引开销。
    

- 建议： 针对大规模部署，倾向于配置更大的段（例如 2GB），以减少管理开销并提升查询速度，前提是查询节点具备足够的内存。同时，应避免过于频繁地刷新段，以降低不必要的压缩开销。
    

3. Woodpecker WAL 显著优化写入性能和成本： Milvus 2.6 引入的 Woodpecker WAL 通过内部化预写日志机制，消除了对外部消息队列的依赖，从而大幅提升了数据摄取吞吐量并降低了延迟。
    

- 建议： 对于写入密集型或对数据新鲜度要求高的应用，应优先考虑使用 Milvus 2.6 及更高版本，以利用 Woodpecker WAL 带来的性能和成本优势。
    

4. 智能索引选择和量化技术至关重要： 不同的向量索引类型（如 HNSW、IVF、FLAT）在内存占用、磁盘 I/O、查询速度和准确性之间存在固有权衡。向量量化技术（SQ、BQ、PQ）通过压缩向量，显著减少了存储占用和内存消耗，从而降低了成本并提升了性能，尽管可能带来一定的准确性损失。
    

- 建议：
    

- 根据数据集规模、查询延迟要求和准确性容忍度，审慎选择合适的索引类型。对于内存受限但需要高召回率的大型数据集，DISKANN 是一个理想选择。
    
- 积极采用向量量化技术，特别是对于大规模数据集，以优化内存和存储成本。应结合过采样、重新评分等策略来缓解量化带来的准确性下降。
    
- 利用 Milvus 的资源估算工具来预测不同索引类型和量化配置下的资源需求，并进行实际的负载测试以验证和微调配置。
    

5. SSD 适配是性能优化的核心： 对于超出内存容量的大型数据集，将索引数据存储在 SSD 上是必然选择。特别是 NVMe SSD，其高速读写能力对于降低查询延迟至关重要，尤其是在使用 DISKANN 等磁盘辅助索引时。
    

- 建议： 确保 Milvus 的数据目录（特别是查询节点和索引节点的数据目录）挂载在高性能 NVMe SSD 上，以最大化 DISKANN 等索引的性能。
    

6. 缓存机制是提升查询响应的关键： Milvus 的分块缓存和查询节点内存缓存能够有效减少查询延迟和后端负载。语义缓存作为一种新兴策略，通过理解查询的语义相似性，进一步提高了缓存命中率。
    

- 建议：
    

- 配置 Milvus 的分块缓存预热策略（sync 或 async），以优化数据加载后的查询体验。
    
- 持续监控缓存使用情况和命中率，并根据需要调整缓存大小和逐出策略。
    
- 对于应用程序层面，可以考虑实现语义缓存，以应对自然语言查询的细微变化，进一步提升缓存效率和用户体验。
    

7. 内存映射 I/O (mmap) 需谨慎权衡： queryNode.mmap 参数可以显著降低 RAM 占用，但会增加对底层磁盘 I/O 的依赖。
    

- 建议： 仅在内存资源极为受限时考虑启用 mmap，并确保底层存储（SSD）能够提供足够的 I/O 吞吐量，以避免将性能瓶颈从内存转移到磁盘。应密切监控磁盘性能指标。
    

综上所述，Milvus 在存储优化方面提供了丰富的工具和配置选项。通过深入理解其架构原理、索引机制、量化技术、SSD 适配策略以及缓存管理，并根据具体应用场景进行精细化配置和持续优化，可以构建出高性能、高可扩展且经济高效的向量搜索系统。

#### 引用的著作

1. What Are Vector Databases and How Do They Work? - InterSystems, 访问时间为 六月 25, 2025， [https://www.intersystems.com/resources/what-are-vector-databases-and-how-do-they-work/](https://www.intersystems.com/resources/what-are-vector-databases-and-how-do-they-work/)
    
2. Vector databases explained: Use cases, algorithms and key features - NetApp Instaclustr, 访问时间为 六月 25, 2025， [https://www.instaclustr.com/education/vector-database/vector-databases-explained-use-cases-algorithms-and-key-features/](https://www.instaclustr.com/education/vector-database/vector-databases-explained-use-cases-algorithms-and-key-features/)
    
3. Vector Database: Everything You Need to Know - WEKA, 访问时间为 六月 25, 2025， [https://www.weka.io/learn/guide/ai-ml/vector-dabase/](https://www.weka.io/learn/guide/ai-ml/vector-dabase/)
    
4. Vector Databases vs. In-Memory Databases - Zilliz blog, 访问时间为 六月 25, 2025， [https://zilliz.com/blog/vector-database-vs-in-memory-databases](https://zilliz.com/blog/vector-database-vs-in-memory-databases)
    
5. Milvus Architecture: Exploring Vector Database Internals, 访问时间为 六月 25, 2025， [https://minervadb.xyz/milvus-architecture/](https://minervadb.xyz/milvus-architecture/)
    
6. Milvus CacheMiss - Doctor Droid, 访问时间为 六月 25, 2025， [https://drdroid.io/stack-diagnosis/milvus-cachemiss](https://drdroid.io/stack-diagnosis/milvus-cachemiss)
    
7. What is Milvus | Milvus Documentation, 访问时间为 六月 25, 2025， [https://milvus.io/docs/overview.md](https://milvus.io/docs/overview.md)
    
8. An Introduction to Milvus Architecture - Zilliz blog, 访问时间为 六月 25, 2025， [https://zilliz.com/blog/introduction-to-milvus-architecture](https://zilliz.com/blog/introduction-to-milvus-architecture)
    
9. How do systems like Milvus facilitate scaling in practice—what components do they provide for clustering, load balancing, or distributed index storage?, 访问时间为 六月 25, 2025， [https://milvus.io/ai-quick-reference/how-do-systems-like-milvus-facilitate-scaling-in-practicewhat-components-do-they-provide-for-clustering-load-balancing-or-distributed-index-storage](https://milvus.io/ai-quick-reference/how-do-systems-like-milvus-facilitate-scaling-in-practicewhat-components-do-they-provide-for-clustering-load-balancing-or-distributed-index-storage)
    
10. How a vector index works and 5 critical best practices - NetApp Instaclustr, 访问时间为 六月 25, 2025， [https://www.instaclustr.com/education/vector-database/how-a-vector-index-works-and-5-critical-best-practices/](https://www.instaclustr.com/education/vector-database/how-a-vector-index-works-and-5-critical-best-practices/)
    
11. Introducing the Milvus Sizing Tool: Calculating and Optimizing Your Milvus Deployment Resources, 访问时间为 六月 25, 2025， [https://milvus.io/blog/introducing-the-milvus-sizing-tool-calculating-and-optimizing-your-milvus-deployment-resources.md](https://milvus.io/blog/introducing-the-milvus-sizing-tool-calculating-and-optimizing-your-milvus-deployment-resources.md)
    
12. The Developer's Guide to Milvus Configuration, 访问时间为 六月 25, 2025， [https://milvus.io/blog/the-developers-guide-to-milvus-configuration.md](https://milvus.io/blog/the-developers-guide-to-milvus-configuration.md)
    
13. How do vector databases like Milvus or Weaviate handle storage of vectors and indexes under the hood (e.g., do they use memory-mapped files, proprietary storage engines, etc.)?, 访问时间为 六月 25, 2025， [https://milvus.io/ai-quick-reference/how-do-vector-databases-like-milvus-or-weaviate-handle-storage-of-vectors-and-indexes-under-the-hood-eg-do-they-use-memorymapped-files-proprietary-storage-engines-etc](https://milvus.io/ai-quick-reference/how-do-vector-databases-like-milvus-or-weaviate-handle-storage-of-vectors-and-indexes-under-the-hood-eg-do-they-use-memorymapped-files-proprietary-storage-engines-etc)
    
14. Milvus 2.6: Built for Scale, Designed to Reduce Costs | Morningstar, 访问时间为 六月 25, 2025， [https://www.morningstar.com/news/globe-newswire/9467544/milvus-26-built-for-scale-designed-to-reduce-costs](https://www.morningstar.com/news/globe-newswire/9467544/milvus-26-built-for-scale-designed-to-reduce-costs)
    
15. Introducing Milvus 2.6: Affordable Vector Search at Billion Scale, 访问时间为 六月 25, 2025， [https://milvus.io/blog/introduce-milvus-2-6-built-for-scale-designed-to-reduce-costs.md](https://milvus.io/blog/introduce-milvus-2-6-built-for-scale-designed-to-reduce-costs.md)
    
16. Vector Indexing | Weaviate, 访问时间为 六月 25, 2025， [https://weaviate.io/developers/weaviate/concepts/vector-index](https://weaviate.io/developers/weaviate/concepts/vector-index)
    
17. Index Explained | Milvus Documentation, 访问时间为 六月 25, 2025， [https://milvus.io/docs/index-explained.md](https://milvus.io/docs/index-explained.md)
    
18. What methods can be used to estimate the storage size of an index before building it (based on number of vectors, dimension, and chosen index type)? - Milvus, 访问时间为 六月 25, 2025， [https://milvus.io/ai-quick-reference/what-methods-can-be-used-to-estimate-the-storage-size-of-an-index-before-building-it-based-on-number-of-vectors-dimension-and-chosen-index-type](https://milvus.io/ai-quick-reference/what-methods-can-be-used-to-estimate-the-storage-size-of-an-index-before-building-it-based-on-number-of-vectors-dimension-and-chosen-index-type)
    
19. Index Vector Fields | Milvus Documentation, 访问时间为 六月 25, 2025， [https://milvus.io/docs/index-vector-fields.md](https://milvus.io/docs/index-vector-fields.md)
    
20. How does indexing work in a vector DB (IVF, HNSW, PQ, etc.)?, 访问时间为 六月 25, 2025， [https://milvus.io/ai-quick-reference/how-does-indexing-work-in-a-vector-db-ivf-hnsw-pq-etc](https://milvus.io/ai-quick-reference/how-does-indexing-work-in-a-vector-db-ivf-hnsw-pq-etc)
    
21. Manage vector indexes | BigQuery - Google Cloud, 访问时间为 六月 25, 2025， [https://cloud.google.com/bigquery/docs/vector-index](https://cloud.google.com/bigquery/docs/vector-index)
    
22. IVFFlat Index - Write You a Vector Database, 访问时间为 六月 25, 2025， [https://skyzh.github.io/write-you-a-vector-db/cpp-05-ivfflat.html](https://skyzh.github.io/write-you-a-vector-db/cpp-05-ivfflat.html)
    
23. How does vector search manage memory usage? - Milvus, 访问时间为 六月 25, 2025， [https://milvus.io/ai-quick-reference/how-does-vector-search-manage-memory-usage](https://milvus.io/ai-quick-reference/how-does-vector-search-manage-memory-usage)
    
24. HNSW index in depth - Weaviate, 访问时间为 六月 25, 2025， [https://weaviate.io/developers/academy/py/vector_index/hnsw](https://weaviate.io/developers/academy/py/vector_index/hnsw)
    
25. Using HNSW Vector Indexes in AI Vector Search - Oracle Blogs, 访问时间为 六月 25, 2025， [https://blogs.oracle.com/database/post/using-hnsw-vector-indexes-in-ai-vector-search](https://blogs.oracle.com/database/post/using-hnsw-vector-indexes-in-ai-vector-search)
    
26. GPU Index Overview | Milvus Documentation, 访问时间为 六月 25, 2025， [https://milvus.io/docs/gpu-index-overview.md](https://milvus.io/docs/gpu-index-overview.md)
    
27. What is Vector Quantization? - Qdrant, 访问时间为 六月 25, 2025， [https://qdrant.tech/articles/what-is-vector-quantization/](https://qdrant.tech/articles/what-is-vector-quantization/)
    
28. Compression (Vector Quantization) | Weaviate, 访问时间为 六月 25, 2025， [https://weaviate.io/developers/weaviate/concepts/vector-quantization](https://weaviate.io/developers/weaviate/concepts/vector-quantization)
    
29. DiskANN Explained - Milvus Blog, 访问时间为 六月 25, 2025， [https://milvus.io/blog/diskann-explained.md](https://milvus.io/blog/diskann-explained.md)
    
30. DISKANN | Milvus Documentation, 访问时间为 六月 25, 2025， [https://milvus.io/docs/diskann.md](https://milvus.io/docs/diskann.md)
    
31. What is the impact of using disk-based ANN methods (where part of the index is on SSD/HDD) on query latency compared to fully in-memory indices? - Milvus, 访问时间为 六月 25, 2025， [https://milvus.io/ai-quick-reference/what-is-the-impact-of-using-diskbased-ann-methods-where-part-of-the-index-is-on-ssdhdd-on-query-latency-compared-to-fully-inmemory-indices](https://milvus.io/ai-quick-reference/what-is-the-impact-of-using-diskbased-ann-methods-where-part-of-the-index-is-on-ssdhdd-on-query-latency-compared-to-fully-inmemory-indices)
    
32. What caching strategies work well with repeated queries? - Milvus, 访问时间为 六月 25, 2025， [https://milvus.io/ai-quick-reference/what-caching-strategies-work-well-with-repeated-queries](https://milvus.io/ai-quick-reference/what-caching-strategies-work-well-with-repeated-queries)
    
33. What role does caching play in improving recommendation performance? - Milvus, 访问时间为 六月 25, 2025， [https://milvus.io/ai-quick-reference/what-role-does-caching-play-in-improving-recommendation-performance](https://milvus.io/ai-quick-reference/what-role-does-caching-play-in-improving-recommendation-performance)
    
34. What is the role of caching in relational databases? - Milvus, 访问时间为 六月 25, 2025， [https://milvus.io/ai-quick-reference/what-is-the-role-of-caching-in-relational-databases](https://milvus.io/ai-quick-reference/what-is-the-role-of-caching-in-relational-databases)
    
35. Unveiling the Power of Semantic Cache in Qdrant DB for Scalable Vector Search – Blog, 访问时间为 六月 25, 2025， [https://blog.miraclesoft.com/unveiling-the-power-of-semantic-cache-in-qdrant-db-for-scalable-vector-search/](https://blog.miraclesoft.com/unveiling-the-power-of-semantic-cache-in-qdrant-db-for-scalable-vector-search/)
    
36. How can caching mechanisms be used in RAG to reduce latency, and what types of data might we cache (embeddings, retrieved results for frequent queries, etc.)? - Milvus, 访问时间为 六月 25, 2025， [https://milvus.io/ai-quick-reference/how-can-caching-mechanisms-be-used-in-rag-to-reduce-latency-and-what-types-of-data-might-we-cache-embeddings-retrieved-results-for-frequent-queries-etc](https://milvus.io/ai-quick-reference/how-can-caching-mechanisms-be-used-in-rag-to-reduce-latency-and-what-types-of-data-might-we-cache-embeddings-retrieved-results-for-frequent-queries-etc)
    
37. Configure Chunk Cache | Milvus Documentation, 访问时间为 六月 25, 2025， [https://milvus.io/docs/chunk_cache.md](https://milvus.io/docs/chunk_cache.md)
    
38. How can I optimize vector search for large datasets? - Milvus, 访问时间为 六月 25, 2025， [https://milvus.io/ai-quick-reference/how-can-i-optimize-vector-search-for-large-datasets](https://milvus.io/ai-quick-reference/how-can-i-optimize-vector-search-for-large-datasets)
    
39. How do I implement caching for semantic search? - Milvus, 访问时间为 六月 25, 2025， [https://milvus.io/ai-quick-reference/how-do-i-implement-caching-for-semantic-search](https://milvus.io/ai-quick-reference/how-do-i-implement-caching-for-semantic-search)
    
40. How do you implement efficient caching for multimodal search? - Milvus, 访问时间为 六月 25, 2025， [https://milvus.io/ai-quick-reference/how-do-you-implement-efficient-caching-for-multimodal-search](https://milvus.io/ai-quick-reference/how-do-you-implement-efficient-caching-for-multimodal-search)
    
41. How Write Amplification Impacts SSD Performance: Key Insights ..., 访问时间为 六月 25, 2025， [https://chat2db.ai/resources/blog/write-amplification-ssd-performance](https://chat2db.ai/resources/blog/write-amplification-ssd-performance)
    

  
  
  
  
  
  
  
  
# Milvus：可伸缩向量搜索的架构创新与性能增强
  >by Gemini
  

## 执行摘要

  

本报告全面概述了 Milvus，一个高性能、云原生的向量数据库，并详细阐述了其重要的架构创新和性能增强。Milvus 专为可伸缩向量相似性搜索而设计，是现代 AI 应用的关键基础设施，持续演进以应对管理海量高维向量数据的复杂挑战 1。

Milvus 的进步涵盖了几个关键领域：

- 云原生架构： 高度解耦的分层设计，将计算与存储分离，实现独立扩展和强大的容错能力 3。
    
- 高级索引： 引入并优化了多样化的索引类型，包括用于高效大规模磁盘搜索的 DiskANN，用于大幅减少内存占用且召回率损失最小的各种量化技术（标量、二进制、乘积以及创新的 RaBitQ），以及用于极致性能的 GPU 加速索引 5。
    
- 优化存储与内存管理： 实现了冷热数据分离的分层存储，智能利用内存映射 I/O（mmap），以及复杂的多层缓存机制，以平衡成本和性能 10。
    
- 性能增强： 通过 Woodpecker 预写日志（WAL）系统简化数据摄取和 JSON Path Index 加速元数据过滤等功能，显著提高了搜索吞吐量和降低了延迟 5。
    

总而言之，这些改进使 Milvus 能够高效处理数十亿向量的数据集，以更低的成本提供高召回率和低延迟。这使得 Milvus 成为生产环境中关键的生成式 AI、推荐系统和语义搜索应用的首选 1。

  

## Milvus 与向量数据库简介

  
  

### 向量数据库的宗旨与核心概念

  

向量数据库是专门设计用于存储、管理和查询高维向量嵌入的数据库管理系统 18。这些数值表示由机器学习模型生成，能够有效地捕捉非结构化数据（如文本、图像、音频和视频）的语义含义、上下文细微差别和底层关系 18。

与为结构化数据和精确关键词匹配而优化的传统关系型数据库不同，向量数据库擅长执行“相似性搜索”或“最近邻搜索” 18。这种能力使其能够识别和检索与给定查询向量在语义或感知上相似的数据点，超越了字面字符串匹配的限制 16。向量数据库中使用的主要相似性度量包括余弦相似度（衡量向量之间的角度）、欧几里得距离（L2，衡量直线距离）和内积（IP，衡量一个向量在另一个向量上的投影） 19。度量方法的选择取决于嵌入的特性和所需的相似性解释。

这种对语义搜索的强调，标志着信息检索和 AI 应用处理方式的一个根本性转变。向量嵌入能够捕捉数据点之间的深层含义和上下文关联，使得系统能够理解用户意图，而不仅仅是匹配关键词。例如，传统关键词搜索“最佳披萨餐厅”可能只返回包含这些确切词语的结果，而语义搜索则能找到任何关于高度推荐披萨店的结果，即使内容中没有使用这些确切词语 16。这种从字面匹配到概念理解的转变，使得 AI 应用能够进行更直观、更像人类的交互。这对于检索增强生成（RAG）、个性化推荐系统和智能内容发现等高级应用至关重要，代表着一种更深层次的信息处理形式。

  

### Milvus 的作用与部署选项

  

Milvus 作为一个杰出的开源、云原生向量数据库，专为可伸缩的近似最近邻（ANN）搜索而设计 1。它最初由 Zilliz 开发，后贡献给 Linux 基金会，这凸显了其社区驱动和强大稳定的特性 16。

Milvus 提供一系列部署选项，以适应从初始开发原型到大规模企业级生产环境的各种用例，确保了高度的适应性和清晰的升级路径。

- Milvus Lite： 这是最轻量级的版本，作为一个 Python 库提供，可无缝集成到本地开发环境、Jupyter Notebook 和边缘设备中。它支持与其他 Milvus 部署相同的核心 API，实现了开发工作流的一致性。虽然非常适合快速原型开发和小型数据集（通常少于一百万向量），但其索引类型支持有限（仅支持 FLAT，从 2.4.11 版本开始支持 IVF_FLAT），并且不支持分区或基于角色的访问控制（RBAC）等高级功能。
    
- Milvus Standalone： 这是一个单机服务器部署，所有 Milvus 组件都打包在一个 Docker 镜像中，简化了部署。此选项适用于不需要 Kubernetes 支持的小型生产工作负载、持续集成/持续部署（CI/CD）流水线或离线场景。它能有效管理从数百万到数亿向量的数据集。
    
- Milvus Distributed（集群）： 这是企业级部署，设计为基于 Kubernetes 集群的云原生分布式向量数据库。其架构特点是组件解耦，确保了高可伸缩性、可用性和容错能力。它旨在处理海量数据集，支持数十亿向量和高查询每秒（QPS）率，是大型生产系统的首选。
    
- Zilliz Cloud： 作为 Milvus 的全托管版本，Zilliz Cloud 提供无忧体验，包括无服务器、专用和自带云（BYOC）部署选项。它旨在抽象化操作复杂性，与自托管 Milvus 实例相比，可能提供显著更快的性能（例如，快 10 倍），是优先考虑应用开发而非基础设施管理组织的理想选择。
    

这种多层次的部署策略，以及跨不同部署模式保持核心 API 的一致性，体现了 Milvus 在优化开发者体验和加速采用方面的深思熟虑。开发者可以从 Milvus Lite 开始快速原型开发和学习，然后随着应用规模的增长，无缝过渡到 Standalone 或 Distributed 版本，而无需重写大量代码。这种方法显著降低了新用户的入门门槛，同时为应用从概念到大规模生产的增长提供了清晰、强大且可伸缩的路径。这表明 Milvus 的设计理念超越了技术功能本身，涵盖了整个开发和运营生命周期，从而促进了其广泛使用和社区发展。

  

## Milvus 架构：深入探讨可伸缩性

  
  

### 云原生设计与分层架构

  

Milvus 的核心设计是云原生系统，旨在充分利用公共云环境提供的灵活性和弹性资源分配能力。其架构模块化且高度解耦，严格遵循计算与存储分离的原则 23。

这种分离式架构包含四个主要层，每层都设计为可独立扩展并具备灾难恢复能力：

- 访问层（Proxy）： 由无状态代理节点组成，该层作为系统的前端和客户端交互的主要入口点。代理负责验证传入的客户端请求，将其高效路由到适当的工作节点，并聚合/后处理来自不同组件的中间结果，然后将最终响应返回给客户端。它提供统一的服务地址，通常利用 Nginx 或 Kubernetes Ingress 等负载均衡组件。
    
- 协调层： 通常被称为 Milvus 集群的“大脑”，该层对于维护系统整体状态至关重要。它包括各种协调器类型：根协调器（管理 DDL/DCL 操作和集合元数据）、数据协调器（跟踪段信息并协调数据节点）、查询协调器（管理查询节点状态和段分配以实现负载均衡）和索引协调器（维护索引元数据并协调索引构建任务）。这些协调器可以有多个实例以提高可靠性，并且不同的集合可以由独立的协调器实例提供服务以提高吞吐量。
    
- 工作层： 该层执行数据库的核心计算任务。工作节点设计为无状态，操作从共享存储层获取的只读数据副本。这种设计允许这些计算密集型节点轻松进行水平扩展。工作层包括：查询节点（处理搜索查询和数据检索）、数据节点（管理新数据摄取、存储和复制）和索引节点（负责构建和管理向量索引）。每种工作节点类型都可以根据不同的工作负载需求和质量服务（QoS）要求独立扩展。
    
- 存储层： 这个基础层确保所有系统数据的持久性。它利用 etcd（一个分布式键值存储）来托管协调器所需的关键系统状态和元数据，提供高可用性、强一致性和事务支持。对于大量数据，包括 binlog、原始向量数据和索引文件，Milvus 利用成本效益高的对象存储服务，如 MinIO、AWS S3 或 Azure Blob。
    

这种架构选择，即计算与存储层的完全分离以及独立可扩展的组件，是 Milvus 优化总拥有成本（TCO）和实现弹性的关键。通过允许查询、数据摄取和索引等不同工作负载独立扩展，系统可以精确分配资源，避免为不常使用的组件过度配置。例如，对于读密集型搜索，可以独立增加查询节点；对于写密集型摄取，则可以增加数据节点。这种精细的资源控制直接优化了基础设施成本。此外，这种架构也是对向量数据操作计算密集型特性以及性能与一致性之间权衡的直接、复杂的回应 3。它标志着一种成熟的设计，专门为向量数据库的独特需求量身定制，超越了传统单体数据库范式的限制，在云环境中实现了无与伦比的弹性和资源效率。

  

### 职责分离：查询、数据摄取与索引节点

  

Milvus 的设计明确分离了向量数据库的三个主要功能领域：查询、数据摄取和索引。每个功能都由专用的节点类型处理，从而实现优化的资源分配和独立扩展。

- 查询节点： 这些节点主要负责执行搜索查询和检索相关向量数据。它们管理各种数据段的内存中索引，并在并行化搜索中发挥关键作用，通过委托、聚合和处理来自多个段的搜索结果来完成此任务，这些段可能位于不同节点上。
    
- 数据节点： 这些节点管理新数据的摄取及其持久存储。它们负责将向量数据和相关元数据写入底层持久存储层，并确保数据复制以实现容错。
    
- 索引节点： 这些节点旨在分担计算密集型向量索引构建任务。一旦收到数据段已密封并刷新到存储的通知，索引节点将直接从存储层读取该特定数据段。这种设置允许索引节点仅处理索引创建所需的必要属性，从而最大限度地减少读取放大并优化索引过程。
    

这些工作节点被明确描述为“无状态”组件。这意味着它们不将操作状态存储在本地，而是从共享的持久存储层获取只读数据副本。这种设计带来了显著的弹性优势。如果一个无状态工作节点发生故障，它可以立即被另一个实例替换，而不会丢失任何正在进行的数据或状态，因为其状态已经被外部化并持久化。这显著增强了系统的韧性和恢复时间 10。此外，无状态特性简化了水平扩展。新实例可以根据需求波动快速启动或关闭，而无需复杂的同步或数据迁移，使得系统具有高度弹性 10。这种设计模式是现代云原生架构的基石，被 Milvus 战略性地应用，确保了高可用性并简化了操作管理，这对于需要持续运行和适应动态工作负载的生产级 AI 应用至关重要。

  

### 数据管理：增长中与已密封段、预写日志（Woodpecker）

  

Milvus 将传入数据组织成名为“段”的逻辑单元，这些是预定义的数据块（默认为 512MB，但可通过 dataCoord.segment.maxSize 配置）。这种基于段的方法是 Milvus 灵活性、可伸缩性和高效数据变异的基础 3。

- 增长中段： 当新数据摄取到系统中时，它最初被引导到查询节点和数据节点中的“增长中段”。这些段临时保存传入数据，直到它们累积到预定义的容量或达到指定的时间限制。
    
- 已密封段： 一旦增长中段在数据节点中达到其预定义容量，它就会转换为“已密封”状态。已密封段随后从数据节点和查询节点刷新到永久对象存储层。在此之后，索引节点会收到通知，开始专门为这些新密封的段构建索引。
    
- 预写日志（WAL）： 作为确保分布式系统中数据持久性和一致性的关键组件，WAL 在所有数据更改提交之前都会对其进行记录。这种机制保证了在系统故障时，数据可以恢复到其最后一致的状态 4。
    
- Woodpecker： Milvus 2.6 引入了 Woodpecker，一个轻量级、云原生的 WAL 系统，代表了重要的架构演进。Woodpecker 消除了对传统用于 WAL 的外部消息队列（如 Kafka 或 Pulsar）的依赖。它采用“零磁盘”设计，直接写入对象存储（例如 S3、MinIO）。这种方法不仅能轻松地随数据摄取需求扩展，还通过消除管理 WAL 本地磁盘的开销来简化操作。这项创新显著提高了写入性能和整体系统效率。
    

将 WAL 层与 Woodpecker 进行内部化和优化，并采用云原生、面向对象存储的设计，体现了 Milvus 对架构效率的深刻承诺。这种战略性举措带来了多重优势。首先，它通过消除对独立且通常成本高昂的消息队列基础设施的需求，直接降低了成本 25。其次，它简化了操作，减少了需要管理和监控的组件数量，从而精简了部署和维护过程 25。最重要的是，它显著提升了性能和可伸缩性。Woodpecker 实现了更高的吞吐量（例如，本地文件系统模式下比 Kafka 快 3.5 倍，S3 模式下快 5.8 倍），并通过将流处理与批处理隔离，在高容量数据摄取期间保持稳定的性能 5。这表明 Milvus 在实时数据摄取方面正朝着更集成、更自给自足的解决方案发展，直接应对了云环境中大规模部署的成本、复杂性和性能挑战。

  

## 高级索引策略及其影响

  
  

### 支持的索引类型概述

  

Milvus 为各种近似最近邻（ANN）索引类型提供强大支持，使用户能够精确平衡搜索速度、准确性和内存使用，以适应广泛的应用场景 10。

- FLAT（暴力搜索）： 这是最简单的索引类型，通过对所有向量进行穷举式线性扫描来找到精确的最近邻。它保证 100% 的召回率（准确度 = 1），但其性能与数据集大小呈线性关系，对于非常大的数据集来说计算成本过高。例如，Milvus Lite 为了优化性能，对于小型数据集（小于 100,000 个向量）会自动回退到 FLAT 索引。
    
- 倒排文件（IVF）系列：
    

- 机制： IVF 系列索引使用 K-means 等算法将向量聚类到桶中。在索引过程中，向量被分配到与其最近质心对应的桶中。在查询期间，Milvus 只扫描那些质心与查询向量最接近的桶中的向量嵌入，从而显著缩小搜索空间并降低计算成本，同时保持可接受的准确度 27。
    
- 类型： 该系列包括 IVF_FLAT（基本 IVF）、IVF_SQ8（带标量量化的 IVF）和 IVF_PQ（带乘积量化的 IVF）27。
    
- 权衡： IVF 索引通常非常适合需要快速吞吐量的大型数据集，并且与基于图的索引相比，它们更节省内存 27。然而，它们的准确度可能对初始聚类的质量敏感。
    

- 分层可导航小世界（HNSW）：
    

- 机制： HNSW 构建一个多层图，其中每层都是其下方层的一个子集。顶层稀疏且具有长距离连接，可实现快速全局遍历，而下层更密集且具有短距离连接，用于精确的局部细化。搜索从最高层开始，导航到附近的节点，然后逐步在更低、更密集的层中细化路径 20。
    
- 特性： HNSW 以其卓越的查询速度和高召回率而备受推崇。它具有高度可伸缩性，查询时间复杂度呈对数关系，并通过 max_connections（控制图密度）和 ef/ef_construction（控制搜索广度和构建质量）等可调参数提供了显著的灵活性 26。
    
- 权衡： HNSW 索引通常比 IVF 变体占用更多的内存，因为图结构需要存储 26。
    

- DiskANN： 一种专门的混合索引，高效利用内存和 SSD。它专为管理和搜索超出可用 RAM 的海量数据集而设计 26。
    
- 基于 GPU 的索引： Milvus 利用 GPU 加速来提高高吞吐量和高召回率场景下的向量搜索性能。这包括 GPU_IVF_FLAT、GPU_IVF_PQ、GPU_CAGRA（针对 GPU 优化的图索引）和 GPU_BRUTE_FORCE 等类型 26。
    
- 稀疏向量索引： Milvus 原生支持稀疏向量索引，如 SPARSE_INVERTED_INDEX，用于全文搜索功能（例如 BM25）和学习的稀疏嵌入（例如 SPLADE、BGE-M3）。这允许结合语义和基于关键词的混合搜索 10。
    
- AUTOINDEX： 对于不确定选择哪种索引的用户，Milvus 提供 AUTOINDEX 选项，它会根据数据特性自动选择最佳索引类型（在开源 Milvus 中默认为 HNSW）26。
    

Milvus 支持多达 14 种以上的索引类型，每种类型在性能、准确性和内存占用方面都有不同的特点 27。这种广泛的索引支持并非仅仅是功能列表，而是一种战略性设计选择，直接解决了向量搜索中固有的“可调精度-性能权衡”问题 38。它使用户能够根据其特定工作负载、硬件限制和预算来微调部署，以实现最佳平衡。这种灵活性使得 Milvus 成为一个高度适应和成熟的向量数据库，能够服务于各种苛刻的 AI 用例。它表明 Milvus 对开发者和架构师在优化大规模向量搜索系统时面临的实际挑战有着深刻的理解。

表 1：Milvus 索引类型及其特性

  

|   |   |   |   |   |   |
|---|---|---|---|---|---|
|索引类型|机制/核心思想|内存占用|准确度/召回率权衡|性能特性|理想用例|
|FLAT|穷举式线性搜索|与原始数据大小线性相关|100% 召回率|慢，随数据量线性增长|小型数据集，需要极致精度|
|IVF_FLAT|聚类（K-means）+ 倒排列表|较低，比 HNSW 更节省|可接受的准确度，取决于聚类质量|较快，减少搜索空间|大型数据集，需要快速吞吐量|
|IVF_SQ8|IVF + 标量量化 (8位)|低 (原始数据 28% / 72% 减少)|最小召回率损失 (约 94.9%)|快 (可达 2x 提升)|内存受限但要求较高准确度的场景|
|IVF_PQ|IVF + 乘积量化|非常低 (可达 64x 压缩)|明显召回率下降 (约 0.7)|索引构建可能较慢，查询较快|极致内存压缩，对精度要求不那么高|
|HNSW|多层图结构|高 (原始数据 2-3x)|高召回率 (通常优异)|非常快 (对数时间复杂度)|低延迟查询，高维数据，实时推荐|
|DiskANN|磁盘图 (Vamana) + 内存 PQ|较低 (部分索引在磁盘)|高召回率 (可达 95%)|较快 (毫秒级延迟)，比内存索引略高|数据集超出 RAM 大小，成本敏感的大规模部署|
|GPU_CAGRA|基于 GPU 的图索引|较高 (原始数据 1.8x)|高|极快 (GPU 加速)|追求极致性能，高吞吐量场景|
|GPU_IVF_FLAT|基于 GPU 的 IVF_FLAT|等同原始数据大小|高|快 (GPU 加速)|平衡性能和内存使用的 GPU 场景|
|GPU_IVF_PQ|基于 GPU 的 IVF_PQ|较低 (取决于压缩参数)|较高损失|快 (GPU 加速)|GPU 环境下内存受限，可接受精度损失|
|GPU_BRUTE_FORCE|基于 GPU 的暴力搜索|等同原始数据大小|100% 召回率|极快 (GPU 加速)|追求极致精度，数据集大小适中，GPU 环境|
|稀疏索引|倒排索引 (例如 BM25)|取决于数据稀疏性|适用于全文搜索|针对全文搜索优化|混合搜索 (语义 + 全文)，RAG 应用|

  

### DiskANN：大规模磁盘搜索的优化

  

DiskANN 代表了向量相似性搜索的一种范式转变方法，专门设计用于通过智能利用固态硬盘（SSD）来处理超出可用 RAM 的海量数据集 26。它是一种基于图的近似最近邻（ANN）方法，结合了两种关键技术：Vamana 图和乘积量化（PQ）7。

- 机制：
    

- Vamana 图： 这是核心的基于磁盘的图结构索引。数据点（向量）在图中表示为节点。图的构建首先形成随机连接，然后通过两个关键步骤进行优化：(1) 基于距离修剪冗余边，以优先选择更高质量的连接，由 max_degree 参数控制（限制每个节点的最大边数）。(2) 添加战略性捷径（长距离边）以连接向量空间中相距较远的数据点，使搜索能够快速遍历图并显著加速导航。search_list_size 参数决定了此图细化过程的广度。Vamana 图以及全精度向量嵌入存储在 SSD 上 7。
    
- 乘积量化（PQ）： DiskANN 利用 PQ 将高维向量压缩成更小的“PQ 码”。这些压缩表示存储在内存中，允许在搜索过程中快速进行近似距离计算，而无需立即进行磁盘读取。这种内存中的 PQ 作为指导，提供近似相似性，有助于减少从磁盘访问全精度向量的次数。pq_code_budget_gb_ratio 参数允许管理分配给这些 PQ 码的内存占用 7。
    
- 搜索过程： DiskANN 中的 ANN 搜索通常从选定的入口点开始（例如，接近数据集全局质心的节点）。算法通过从当前节点的边中收集潜在的候选邻居来探索邻域，使用内存中的 PQ 码来近似距离。然后选择最有希望的邻居子集进行精确距离评估，这需要从磁盘读取其原始、未压缩的向量。beam_width_ratio 参数控制此并行搜索的广度，而 search_cache_budget_gb_ratio 管理分配给缓存频繁访问的磁盘数据的内存，从而最大限度地减少重复的磁盘 I/O 8。
    

- 配置与 NVMe SSD 最佳实践：
    

- 默认情况下，Milvus 中禁用 DiskANN，以优先考虑内存中索引的速度，适用于完全适合 RAM 的数据集 8。要启用 DiskANN，必须在  
    milvus.yaml 配置文件中将 queryNode.enableDisk 参数设置为 true 8。
    
- 为了获得 DiskANN 的最佳性能，强烈建议将 Milvus 数据（特别是集群部署中 QueryNode 和 IndexNode 容器的数据）存储在快速 NVMe SSD 上。NVMe 驱动器可确保显著更快的读写速度，这对于 DiskANN 图遍历和索引操作中涉及的频繁磁盘访问至关重要 8。
    
- DiskANN 特定的参数，如 max_degree、search_list_size、pq_code_budget_gb_ratio、search_cache_budget_gb_ratio 和 beam_width_ratio，可以通过 milvus.yaml 配置文件进行通用设置，或通过 Milvus SDK 在索引创建或搜索操作期间进行动态微调，以实现更精细的控制 8。
    

- 权衡：延迟与成本/规模：
    

- DiskANN 为处理数十亿向量提供了一种经济高效的解决方案，与纯内存方法相比，其内存占用显著更小 7。
    
- 然而，由于不可避免的磁盘 I/O 操作开销，即使使用高速 SSD，它也会比完全内存中的索引引入略高的查询延迟（毫秒级 vs 微秒级）7。尽管如此，考虑到大规模数据集的巨大成本节约和可伸缩性优势，这种权衡通常是可接受且非常有益的 7。
    

Milvus 明确推荐将“快速 NVMe SSD”用于 DiskANN 8。DiskANN 是一种基于图的索引，存储在磁盘上，并在搜索遍历期间执行“随机 I/O”7。它需要每次读取请求获取多个节点 7。NVMe SSD 在随机读/写性能和延迟方面明显优于传统的 SATA SSD 或 HDD 39。DiskANN 图遍历的效率，涉及对磁盘驻留节点及其嵌入的大量随机访问，直接受到底层存储随机 I/O 能力的限制。NVMe 在处理高 IOPS 和小而随机读取的低延迟方面的架构优势，直接转化为更好的 DiskANN 性能。因此，这种针对 DiskANN 的特定硬件推荐并非仅仅是一个建议，而是实现“数十亿规模”性能的关键架构依赖。它凸显了优化向量数据库以应对如此庞大数据集需要对现代硬件特性有深刻的理解和明确的利用。这表明了一种复杂的硬件-软件协同设计方法，这对于突破 AI 高性能计算的界限至关重要。

  

### 量化技术提升内存与性能效率

  

向量量化（VQ）是一种基本的数据压缩技术，用于减小高维向量数据的大小。这种减小直接转化为更低的内存使用和显著更快的搜索操作，这对于大型数据集尤为关键 37。Milvus 与其他领先的向量数据库一样，广泛集成并优化了各种 VQ 方法 27。

- 标量量化（SQ）：
    

- 存储减少： SQ 将 32 位浮点值（通常每个维度占用 4 字节）映射到 8 位整数（1 字节）。这导致内存大小大幅减少 75%，即 4 倍压缩比 27。Milvus 2.6 引入了优化版本 SQ8 Refine 5。
    
- 对准确度的影响： SQ 旨在将准确度损失降至最低。例如，quantile 等参数可以调整以微调量化边界并管理精度 37。它通常比二进制量化提供更高的准确度 40。
    
- 对性能的影响： SQ 提升了搜索速度和压缩效率。使用 int8 值进行距离计算在计算上更简单，从而带来高达 2 倍的性能提升 37。
    

- 二进制量化（BQ）：
    

- 存储减少： BQ 将高维向量转换为高度紧凑的二进制（0 或 1）表示。每个向量维度（通常为 32 位）减少到仅 1 位，实现了惊人的 32 倍存储需求减少 37。
    
- 对准确度的影响： 由于激进的压缩，BQ 在精度方面涉及更大的权衡。通常建议将其用于至少 1024 维的模型（例如 OpenAI 的 text-embedding-ada-002），以最大限度地减少准确度损失，兼容模型的报告准确度约为 0.95 37。
    
- 对性能的影响： BQ 在量化方法中提供了最显著的处理速度提升。其二进制表示允许系统使用高度优化的 CPU 指令（如 XOR 和 Popcount）进行极快的距离计算，根据数据集和硬件，搜索操作可加速高达 40 倍 37。
    

- 乘积量化（PQ）：
    

- 存储减少： PQ 通过将高维向量分成更小的子向量来压缩它们。对于每个子向量，都会创建一个单独的质心码本（由 K-means 聚类算法确定）。然后将原始子向量映射到其各自码本中最近的质心，压缩向量存储这些质心的索引。该技术在某些配置下可提供高达 64 倍的压缩（例如，将 1024 维向量从 4096 字节减少到 128 字节）42。
    
- 对准确度的影响： 由于其高压缩级别，PQ 可能导致搜索质量显著下降（报告准确度约为 0.7）。这使得它不适用于对精度要求极高的应用 6。
    
- 对性能的影响： 尽管 PQ 提供了最高的压缩率，但可能导致索引速度变慢 37。
    

- RaBitQ（1 位）量化（Milvus 2.6 创新）： Milvus 2.6 引入了 RaBitQ，一种专门的 1 位量化技术，旨在将压缩推向极致。当与 SQ8 Refine 结合使用时，RaBitQ 实现了卓越的 97% 内存减少（将内存占用减少到基线的 3%），同时保持了约 94.9% 的高召回质量。这种组合还显著提高了 4 倍的查询吞吐量（QPS），使用户能够以 75% 更少的服务器提供相同的工作负载，或在现有基础设施上处理四倍的流量。
    
- 缓解准确度损失（重排序、过采样、重新排名）：
    

- 由于量化是一种有损压缩技术，原始向量中的一些细节会被删除，这可能会略微降低搜索准确度。为了抵消这一点，Milvus 和其他向量数据库采用了多种技术 37。
    
- 过采样： 这种技术涉及在初始快速量化搜索中检索比所需最终结果限制更多的候选向量（例如，如果所需限制为 4 且过采样因子为 2，则检索 8 个候选）。这增加了相关向量进入最终结果池的可能性 37。
    
- 使用原始向量重排序： 过采样后，使用其对应的原始（未量化）向量重新评估检索到的候选。这允许进行更精确的距离计算，并考虑初始压缩搜索中未捕获的因素。此过程显著更快，因为它只涉及从磁盘读取少量向量 37。
    
- 重新排名： 根据重排序步骤中精炼的相似性分数，确定并呈现最终的 Top-K 候选。在量化搜索中最初排名较低的候选，在重排序后可能会由于原始向量的改进分数而进入 Top 结果 37。
    

量化技术在传统上涉及高压缩率（例如 BQ、PQ）通常会导致显著的准确度损失 6。Milvus 自身的博客中也提到，“大多数现有方法为了节省内存而牺牲了过多的搜索质量” 9。Milvus 2.6 通过引入 RaBitQ 1 位量化与“可调优化能力”（SQ4/SQ6/SQ8 Refine）相结合，有效地解决了这个难题 5。这种结合使得 Milvus 能够在实现极致压缩的同时，保持高召回率（约 94.9%）和显著的吞吐量提升（4 倍 QPS）5。这种方法通过在初始快速量化搜索中进行“过采样”，然后使用原始向量对候选进行“重排序”和“重新排名”，从而弥补了压缩带来的精度损失 37。这种多阶段策略使得 Milvus 能够克服传统量化技术在压缩和准确度之间的固有矛盾，实现了在生产环境中对大规模向量数据进行高效且精确搜索的能力。这种创新不仅降低了基础设施成本，还提升了系统整体性能，使得在内存受限的环境下实现高性能向量搜索成为可能。

  

## 结论

  

本报告深入探讨了 Milvus 作为高性能、云原生向量数据库的架构创新和性能增强。通过对 Milvus 核心设计原则、索引策略、存储管理和最新优化的分析，揭示了其在应对大规模向量数据挑战方面的卓越能力。

Milvus 的云原生架构，以计算与存储分离为核心，通过访问层、协调层、工作层和存储层的独立可伸缩性，显著优化了总拥有成本并提升了系统弹性。这种解耦设计使得资源能够精确分配，避免了传统数据库架构中常见的资源浪费和性能瓶颈。工作节点（查询、数据、索引节点）的无状态特性进一步增强了系统的韧性，确保了高可用性和快速恢复能力，这对于需要持续运行的 AI 应用至关重要。

在数据管理方面，Milvus 通过增长中与已密封段的机制，以及创新的 Woodpecker 预写日志系统，实现了高效的数据摄取和持久化。Woodpecker 取代了对外部消息队列的依赖，直接写入对象存储，不仅降低了基础设施成本和操作复杂性，还在高容量数据摄取期间提供了卓越的吞吐量和稳定性。

Milvus 在索引策略上的多样性是其核心优势之一。从精确的 FLAT 索引到高效的 IVF 系列、高性能的 HNSW，再到专为大规模磁盘搜索设计的 DiskANN，以及各种 GPU 加速索引和稀疏向量索引，Milvus 提供了广泛的选择。这种灵活性使用户能够根据其特定工作负载、硬件限制和精度要求，精细调整性能与准确度的平衡。特别是 DiskANN 索引对 NVMe SSD 的优化利用，体现了 Milvus 在硬件-软件协同设计方面的深度，从而实现了对数十亿向量的有效管理。

此外，Milvus 在量化技术方面的进步，尤其是 Milvus 2.6 中引入的 RaBitQ 1 位量化与 SQ8 Refine 的结合，成功解决了传统量化中高压缩与精度损失之间的矛盾。通过过采样、重排序和重新排名等补偿机制，Milvus 能够在大幅减少内存占用的同时，保持高召回率和显著的查询吞吐量。

综上所述，Milvus 的这些创新共同使其成为处理数十亿向量数据、提供高召回率和低延迟的领先解决方案，并显著降低了基础设施成本。这使其成为构建和部署下一代生成式 AI、推荐系统和语义搜索应用的关键基础设施。

#### 引用的著作

1. Milvus is a high-performance, cloud-native vector database built for scalable vector ANN search - GitHub, 访问时间为 六月 25, 2025， [https://github.com/milvus-io/milvus](https://github.com/milvus-io/milvus)
    
2. Zilliz Pioneers Vector Database R&D, Shares New Findings at VLDB 2022 - Business Wire, 访问时间为 六月 25, 2025， [https://www.businesswire.com/news/home/20220913005080/en/Zilliz-Pioneers-Vector-Database-RD-Shares-New-Findings-at-VLDB-2022](https://www.businesswire.com/news/home/20220913005080/en/Zilliz-Pioneers-Vector-Database-RD-Shares-New-Findings-at-VLDB-2022)
    
3. An Introduction to Milvus Architecture - Zilliz blog, 访问时间为 六月 25, 2025， [https://zilliz.com/blog/introduction-to-milvus-architecture](https://zilliz.com/blog/introduction-to-milvus-architecture)
    
4. Milvus Architecture Overview, 访问时间为 六月 25, 2025， [https://milvus.io/docs/architecture_overview.md](https://milvus.io/docs/architecture_overview.md)
    
5. Introducing Milvus 2.6: Affordable Vector Search at Billion Scale, 访问时间为 六月 25, 2025， [https://milvus.io/blog/introduce-milvus-2-6-built-for-scale-designed-to-reduce-costs.md](https://milvus.io/blog/introduce-milvus-2-6-built-for-scale-designed-to-reduce-costs.md)
    
6. How does indexing work in a vector DB (IVF, HNSW, PQ, etc.)? - Milvus, 访问时间为 六月 25, 2025， [https://milvus.io/ai-quick-reference/how-does-indexing-work-in-a-vector-db-ivf-hnsw-pq-etc](https://milvus.io/ai-quick-reference/how-does-indexing-work-in-a-vector-db-ivf-hnsw-pq-etc)
    
7. DiskANN Explained - Milvus Blog, 访问时间为 六月 25, 2025， [https://milvus.io/blog/diskann-explained.md](https://milvus.io/blog/diskann-explained.md)
    
8. DISKANN | Milvus Documentation, 访问时间为 六月 25, 2025， [https://milvus.io/docs/diskann.md](https://milvus.io/docs/diskann.md)
    
9. Milvus 2.6 Preview: 72% Memory Reduction Without Compromising Recall and 4x Faster Than Elasticsearch, 访问时间为 六月 25, 2025， [https://milvus.io/blog/milvus-26-preview-72-memory-reduction-without-compromising-recall-and-4x-faster-than-elasticsearch.md](https://milvus.io/blog/milvus-26-preview-72-memory-reduction-without-compromising-recall-and-4x-faster-than-elasticsearch.md)
    
10. What is Milvus | Milvus Documentation, 访问时间为 六月 25, 2025， [https://milvus.io/docs/overview.md](https://milvus.io/docs/overview.md)
    
11. The Developer's Guide to Milvus Configuration, 访问时间为 六月 25, 2025， [https://milvus.io/blog/the-developers-guide-to-milvus-configuration.md](https://milvus.io/blog/the-developers-guide-to-milvus-configuration.md)
    
12. How do vector databases like Milvus or Weaviate handle storage of vectors and indexes under the hood (e.g., do they use memory-mapped files, proprietary storage engines, etc.)?, 访问时间为 六月 25, 2025， [https://milvus.io/ai-quick-reference/how-do-vector-databases-like-milvus-or-weaviate-handle-storage-of-vectors-and-indexes-under-the-hood-eg-do-they-use-memorymapped-files-proprietary-storage-engines-etc](https://milvus.io/ai-quick-reference/how-do-vector-databases-like-milvus-or-weaviate-handle-storage-of-vectors-and-indexes-under-the-hood-eg-do-they-use-memorymapped-files-proprietary-storage-engines-etc)
    
13. How does vector search manage memory usage? - Milvus, 访问时间为 六月 25, 2025， [https://milvus.io/ai-quick-reference/how-does-vector-search-manage-memory-usage](https://milvus.io/ai-quick-reference/how-does-vector-search-manage-memory-usage)
    
14. Introducing Milvus 2.6: Affordable Vector Search at Billion Scale, 访问时间为 六月 25, 2025， [https://milvus.io/de/blog/introduce-milvus-2-6-built-for-scale-designed-to-reduce-costs.md](https://milvus.io/de/blog/introduce-milvus-2-6-built-for-scale-designed-to-reduce-costs.md)
    
15. Milvus | High-Performance Vector Database Built for Scale, 访问时间为 六月 25, 2025， [https://milvus.io/](https://milvus.io/)
    
16. What is Milvus? - IBM, 访问时间为 六月 25, 2025， [https://www.ibm.com/think/topics/milvus](https://www.ibm.com/think/topics/milvus)
    
17. Can milvus benefit from indexes which support update/delete #36735 - GitHub, 访问时间为 六月 25, 2025， [https://github.com/milvus-io/milvus/discussions/36735](https://github.com/milvus-io/milvus/discussions/36735)
    
18. What Are Vector Databases and How Do They Work? - InterSystems, 访问时间为 六月 25, 2025， [https://www.intersystems.com/resources/what-are-vector-databases-and-how-do-they-work/](https://www.intersystems.com/resources/what-are-vector-databases-and-how-do-they-work/)
    
19. Vector Database: Everything You Need to Know - WEKA, 访问时间为 六月 25, 2025， [https://www.weka.io/learn/guide/ai-ml/vector-dabase/](https://www.weka.io/learn/guide/ai-ml/vector-dabase/)
    
20. Vector Indexing | Weaviate, 访问时间为 六月 25, 2025， [https://weaviate.io/developers/weaviate/concepts/vector-index](https://weaviate.io/developers/weaviate/concepts/vector-index)
    
21. Index Vector Fields | Milvus Documentation, 访问时间为 六月 25, 2025， [https://milvus.io/docs/index-vector-fields.md](https://milvus.io/docs/index-vector-fields.md)
    
22. Survey of vector database management systems, 访问时间为 六月 25, 2025， [https://dbgroup.cs.tsinghua.edu.cn/ligl/papers/vldbj2024-vectordb.pdf](https://dbgroup.cs.tsinghua.edu.cn/ligl/papers/vldbj2024-vectordb.pdf)
    
23. Milvus Architecture: Exploring Vector Database Internals, 访问时间为 六月 25, 2025， [https://minervadb.xyz/milvus-architecture/](https://minervadb.xyz/milvus-architecture/)
    
24. Manu: A Cloud Native Vector Database Management System - VLDB Endowment, 访问时间为 六月 25, 2025， [https://www.vldb.org/pvldb/vol15/p3548-yan.pdf](https://www.vldb.org/pvldb/vol15/p3548-yan.pdf)
    
25. Milvus 2.6: Built for Scale, Designed to Reduce Costs | Morningstar, 访问时间为 六月 25, 2025， [https://www.morningstar.com/news/globe-newswire/9467544/milvus-26-built-for-scale-designed-to-reduce-costs](https://www.morningstar.com/news/globe-newswire/9467544/milvus-26-built-for-scale-designed-to-reduce-costs)
    
26. Introducing the Milvus Sizing Tool: Calculating and Optimizing Your Milvus Deployment Resources, 访问时间为 六月 25, 2025， [https://milvus.io/blog/introducing-the-milvus-sizing-tool-calculating-and-optimizing-your-milvus-deployment-resources.md](https://milvus.io/blog/introducing-the-milvus-sizing-tool-calculating-and-optimizing-your-milvus-deployment-resources.md)
    
27. Index Explained | Milvus Documentation, 访问时间为 六月 25, 2025， [https://milvus.io/docs/index-explained.md](https://milvus.io/docs/index-explained.md)
    
28. Comparing Vector Databases: Milvus vs. Chroma DB - Zilliz blog, 访问时间为 六月 25, 2025， [https://zilliz.com/blog/milvus-vs-chroma](https://zilliz.com/blog/milvus-vs-chroma)
    
29. Manage vector indexes | BigQuery - Google Cloud, 访问时间为 六月 25, 2025， [https://cloud.google.com/bigquery/docs/vector-index](https://cloud.google.com/bigquery/docs/vector-index)
    
30. IVFFlat Index - Write You a Vector Database, 访问时间为 六月 25, 2025， [https://skyzh.github.io/write-you-a-vector-db/cpp-05-ivfflat.html](https://skyzh.github.io/write-you-a-vector-db/cpp-05-ivfflat.html)
    
31. HNSW index in depth - Weaviate, 访问时间为 六月 25, 2025， [https://weaviate.io/developers/academy/py/vector_index/hnsw](https://weaviate.io/developers/academy/py/vector_index/hnsw)
    
32. Hierarchical Navigable Small Worlds (HNSW) - Pinecone, 访问时间为 六月 25, 2025， [https://www.pinecone.io/learn/series/faiss/hnsw/](https://www.pinecone.io/learn/series/faiss/hnsw/)
    
33. What is the impact of using disk-based ANN methods (where part of the index is on SSD/HDD) on query latency compared to fully in-memory indices? - Milvus, 访问时间为 六月 25, 2025， [https://milvus.io/ai-quick-reference/what-is-the-impact-of-using-diskbased-ann-methods-where-part-of-the-index-is-on-ssdhdd-on-query-latency-compared-to-fully-inmemory-indices](https://milvus.io/ai-quick-reference/what-is-the-impact-of-using-diskbased-ann-methods-where-part-of-the-index-is-on-ssdhdd-on-query-latency-compared-to-fully-inmemory-indices)
    
34. GPU Index Overview | Milvus Documentation, 访问时间为 六月 25, 2025， [https://milvus.io/docs/gpu-index-overview.md](https://milvus.io/docs/gpu-index-overview.md)
    
35. Toward Understanding Bugs in Vector Database ... - arXiv, 访问时间为 六月 25, 2025， [https://arxiv.org/pdf/2506.02617](https://arxiv.org/pdf/2506.02617)
    
36. What Milvus Users Taught Us in 2024, 访问时间为 六月 25, 2025， [https://milvus.io/blog/what-milvus-taught-us-in-2024.md](https://milvus.io/blog/what-milvus-taught-us-in-2024.md)
    
37. What is Vector Quantization? - Qdrant, 访问时间为 六月 25, 2025， [https://qdrant.tech/articles/what-is-vector-quantization/](https://qdrant.tech/articles/what-is-vector-quantization/)
    
38. Vector Databases vs. In-Memory Databases - Zilliz blog, 访问时间为 六月 25, 2025， [https://zilliz.com/blog/vector-database-vs-in-memory-databases](https://zilliz.com/blog/vector-database-vs-in-memory-databases)
    
39. What hardware considerations (using more but cheaper nodes vs fewer powerful nodes, using NVMe SSDs, etc.) come into play when dealing with very large vector indexes? - Milvus, 访问时间为 六月 25, 2025， [https://milvus.io/ai-quick-reference/what-hardware-considerations-using-more-but-cheaper-nodes-vs-fewer-powerful-nodes-using-nvme-ssds-etc-come-into-play-when-dealing-with-very-large-vector-indexes](https://milvus.io/ai-quick-reference/what-hardware-considerations-using-more-but-cheaper-nodes-vs-fewer-powerful-nodes-using-nvme-ssds-etc-come-into-play-when-dealing-with-very-large-vector-indexes)
    
40. Compression (Vector Quantization) | Weaviate, 访问时间为 六月 25, 2025， [https://weaviate.io/developers/weaviate/concepts/vector-quantization](https://weaviate.io/developers/weaviate/concepts/vector-quantization)
    
41. How can I optimize vector search for large datasets? - Milvus, 访问时间为 六月 25, 2025， [https://milvus.io/ai-quick-reference/how-can-i-optimize-vector-search-for-large-datasets](https://milvus.io/ai-quick-reference/how-can-i-optimize-vector-search-for-large-datasets)
    
42. What methods can be used to estimate the storage size of an index before building it (based on number of vectors, dimension, and chosen index type)? - Milvus, 访问时间为 六月 25, 2025， [https://milvus.io/ai-quick-reference/what-methods-can-be-used-to-estimate-the-storage-size-of-an-index-before-building-it-based-on-number-of-vectors-dimension-and-chosen-index-type](https://milvus.io/ai-quick-reference/what-methods-can-be-used-to-estimate-the-storage-size-of-an-index-before-building-it-based-on-number-of-vectors-dimension-and-chosen-index-type)
    

**