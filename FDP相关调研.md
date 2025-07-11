# 平台——FDPvirt
[[Paper_in_CN/FDPVirt|FDPVirt]]   26th CLUSTER 2024: Kobe, Japan - Workshops

基于NVMeVirt(这个我做ZNS用过，开源），新增了对FDP的模拟。
FDPvirt也开源，但是删库了

# 项目&论文
1. FDPFS is a File System in Userspace (FUSE) - based file system that expose FDP SSD's chariteristics to allow ease of use data placement on FDP-enabled SSDs. 暴露FDP SSD的文件系统 [github](https://github.com/pingxiang-chen/fuse-fdpfs.git)
2. 支持FDP SSD的CacheLib（已完成merge） https://github.com/facebook/CacheLib/pull/277.  
3. Towards Efficient Flash Caches with Emerging NVMe Flexibl Data Placement SSDs. [EuroSys 2025](https://dl.acm.org/doi/10.1145/3689031.3696091)

# 问题
1. 手动复现FDPVirt，模拟器的说服力
2. 好处是这个和ZNS有一定交叉，可以用到以前调研的文章。或者和ZNS做对比实验。


> 下面记录了实现FDP需要遵循的标准规范
--- 
# NVMe Flexible Data Placement (FDP) 标准化接口

## 引言

本文分析了 NVMe SSD 中 Flexible Data Placement (FDP) 的用户可操作接口，基于 NVMe 2.0 规范中的技术提案 TP 4146。FDP 是一种主机引导的数据放置技术，旨在优化 SSD 的性能和耐久性，减少写放大因子（WAF）。以下详细说明了 FDP 的标准化接口，包括日志页、特性、命令和寄存器，以及用户如何通过工具操作这些接口。

## 方法与数据

分析过程包括：

- 参考 NVMe 2.0 技术提案 TP 4146，提取 FDP 的命令集和接口定义。
- 分析开源工具（如 NVMe-CLI 和 xNVMe）的文档，验证实际操作接口。

数据来源包括：

- NVMe 2.0 规范（TP 4146），定义了 FDP 的命令和特性。
- xNVMe 文档，提供了 FDP 的 CLI 和编程接口示例。
- NVMe-CLI 手册页，描述了用户友好的命令行工具。
## FDP 的标准化接口

FDP 的接口设计基于 NVMe 命令集，扩展了日志页、特性、命令和寄存器，以支持主机引导的数据放置。以下是详细的接口描述：
### 1. 日志页（Log Pages）
FDP 定义了以下四个日志页，用于获取配置、统计和事件信息。这些日志页是 Endurance Group 范围的，通过 NVMe 的 `Get Log Page` 命令（Opcode：0x02）访问。

|**日志页**|**日志 ID**|**描述**|
|---|---|---|
|FDP Configuration|0x10|提供 FDP 配置信息，包括 Reclaim Unit Handles (RUH) 数量和 Reclaim Group (RG) 信息。|
|Reclaim Unit Handle Usage|0x11|显示当前 RUH 的使用情况，记录每个 RU 的使用状态。|
|FDP Statistics|0x12|提供性能统计数据，如写放大因子（WAF）和写入量。|
|FDP Events|0x13|记录 FDP 相关事件，如垃圾回收（GC）触发的事件。|

**操作示例**：
- 使用 NVMe-CLI 获取 FDP 配置：
    nvme fdp configs /dev/nvme0 --endgrp-id=0x1 --output-format=json
- 使用 xNVMe CLI 获取统计数据：
    xnvme log-fdp-stats /dev/nvme3n1 --lsi 0x1

### 2. 特性（Features）
FDP 定义了两个特性，用于启用/禁用功能和管理事件通知，通过 `Get Features`（Opcode：0x06）和 `Set Features`（Opcode：0x09）命令访问。

|**特性**|**特性 ID**|**描述**|
|---|---|---|
|Flexible Data Placement|0x1d|启用或禁用 FDP 功能，指定配置索引以选择特定的 FDP 配置。|
|FDP Events|0x1e|管理 FDP 事件通知，允许主机选择需要监控的事件类型（如 GC 事件）。|

**操作示例**：

- 启用 FDP 特性：
    nvme fdp feature /dev/nvme0 --enable-conf-idx=1 --endgrp-id=0x1
- 配置 FDP 事件：
    xnvme set-fdp-events /dev/nvme3n1 --fid 0x1e --feat 0x60000 --cdw12 0x1

### 3. 命令（Commands）
FDP 扩展了 NVMe 命令集，增加了对数据放置的支持：

|**命令**|**操作码（Opcode）**|**描述**|
|---|---|---|
|Write|0x01|标准写命令，扩展以包含 Placement Identifier (PID)，指定数据写入的 Reclaim Unit (RU)。|
|I/O Management Send|0x90|更新 Reclaim Unit Handle (RUH) 的状态，用于管理 RU 的分配和回收。|
|I/O Management Receive|0x91|获取 RUH 的状态信息，了解当前 RU 的使用情况。|

**Placement Identifier (PID)**：

- PID 由 Reclaim Group Identifier (RGID) 和 Placement Handle (PH) 组成，用于指定数据写入的 RU。
- 最大支持 128 个 Placement Handles（参考 QEMU 补丁）。

**操作示例**：

- 获取 RUH 状态：
    nvme fdp status /dev/nvme0 --namespace-id=0x1
- 更新 RUH：
    xnvme fdp-ruhu /dev/nvme3n1 --pid 0x0
### 4. 寄存器（Registers）

FDP 使用 NVMe 的寄存器来配置和监控功能：
- **Identify Controller**：包含 FDP 支持信息，如最大 RUH 数量（通常 1 到 128）。
- **日志页寄存器**：用于访问上述日志页的配置和状态数据。

### 5. 开源工具支持

用户可以通过以下工具操作 FDP 接口：
- **NVMe-CLI**：提供用户友好的命令行接口，如：
    
    - `nvme fdp configs`：获取 FDP 配置。
    - `nvme fdp feature`：启用/禁用 FDP 特性。
    - `nvme fdp status`：获取 RUH 状态。
    - `nvme fdp set-events`：配置 FDP 事件。
        
- **xNVMe CLI**：支持更高级的操作，如：
    - `xnvme log-fdp-config`：获取配置日志。
    - `xnvme fdp-ruhs`：获取 RUH 状态。
- **FIO with xNVMe ioengine**：支持 FDP 的 I/O 测试，配置选项包括：
    
    - `fdp=1`：启用 FDP。
    - `fdp_pli=x,y,...`：指定 Placement Identifier 列表。
    - 示例：
        fio xnvme-fdp.fio --section=default --ioengine=xnvme --filename=/dev/ng3n1

### 实现与测试
由于 FDP 是新兴技术，实际硬件支持可能有限。用户可以通过以下方式测试 FDP 接口：
- **仿真工具**：使用基于 NVMeVirt 的 FDPVirt（参考论文 DOI: 10.1145/3704440.3704792）模拟 FDP 功能。
- **硬件支持**：需要支持 FDP 的 NVMe SSD（如 Samsung FDP Prototype SSD）。
- **Linux 内核支持**：FDP 通过 IOUring_Passthru 提供支持，常规块层路径正在开发中（参考 [Linux Kernel Commit]([https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/commit/?id=456cba386e94f22fa1b](https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/commit/?id=456cba386e94f22fa1b) 1426303fdcac9e66b1417)）。
### 讨论
FDP 的接口设计充分利用了 NVMe 命令集的扩展性，通过日志页提供详细的配置和统计信息，通过特性实现功能控制，通过命令支持数据放置的精细管理。这些接口为主机软件提供了灵活性，允许优化数据放置以减少 WAF（论文报告降低高达 26.3%）。NVMe-CLI 和 xNVMe 等工具进一步降低了操作门槛，使开发者能够轻松测试和部署 FDP。
### 结论
FDP 的标准化接口包括日志页（Log ID：0x10-0x13）、特性（Feature ID：0x1d、0x1e）、扩展的写命令（Opcode：0x01）和 I/O 管理命令（Opcode：0x90、0x91），以及相关寄存器。这些接口允许用户配置、监控和管理 FDP 功能，优化 SSD 性能和耐久性。用户可以通过 NVMe-CLI 或 xNVMe 工具操作这些接口，或使用仿真工具（如 FDPVirt）进行研究。未来，随着 FDP 硬件的普及，这些接口将在数据中心和云计算中发挥更大作用。

## 关键引用

- NVM Express Specifications Overview
- Flexible Data Placement FDP Overview
- xNVMe FDP Tutorial
- NVMe-CLI FDP Configs Man Page
- NVMe-CLI FDP Feature Man Page
- NVMe-CLI FDP Status Man Page
- Ubuntu Manpage for NVMe FDP Set Events
- NVMe FDP StorageNewsletter Article
- Linux Kernel Commit for FDP Support