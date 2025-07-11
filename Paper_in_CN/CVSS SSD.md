# 容量可变存储系统（CVSS）的设计与实现

#SSD

## 摘要

固态硬盘（SSD）在使用过程中会经历性能下降，这主要是由于闪存单元的老化导致的。传统的 SSD 设计采用固定容量的抽象，即使在设备老化后也会尝试维持相同的容量，这导致了性能显著下降和可靠性问题。本文提出了一种新的存储系统设计理念——容量可变存储系统（Capacity-Variant Storage System, CVSS），它通过在设备老化时优雅地减少存储容量来保持高性能和可靠性。CVSS 包括三个主要组件：容量可变 SSD（CV-SSD）、容量可变文件系统（CV-FS）和容量可变管理器（CV-manager）。实验结果表明，与现有技术相比，CVSS 能够显著提高性能、延长设备寿命并减少读取重试次数。

## 1. 引言

固态硬盘（SSD）已成为现代存储系统的重要组成部分，但它们面临着使用寿命有限的问题。随着使用时间的增加，SSD 的性能会逐渐下降，这主要是由于闪存单元的老化导致的。当闪存单元老化时，它们的读取延迟增加，需要更多的读取重试和更强的纠错能力，这导致了整体性能的下降。

传统的 SSD 设计采用固定容量的抽象，即使在设备老化后也会尝试维持相同的容量。这种设计导致了两个主要问题：

1. 性能下降 ：为了维持固定容量，SSD 必须使用所有可用的闪存块，包括那些已经老化的块。这导致了读取延迟增加和写入放大因子（WAF）上升。
2. 可靠性问题 ：使用老化的闪存块增加了数据丢失的风险，因为这些块更容易出现不可恢复的错误。
   本文提出了一种新的存储系统设计理念——容量可变存储系统（CVSS），它通过在设备老化时优雅地减少存储容量来保持高性能和可靠性。CVSS 的核心思想是，随着 SSD 的老化，系统会逐渐减少可用的逻辑容量，将老化严重的闪存块从活跃数据存储中排除，从而保持整体性能和可靠性。

## 2. 背景与动机

### 2.1 SSD 性能下降问题

SSD 的性能下降主要是由以下因素导致的：

- 闪存单元老化 ：随着程序/擦除（P/E）循环的增加，闪存单元的电子陷阱增多，导致读取延迟增加和错误率上升。
- 读取重试 ：当读取操作失败时，SSD 控制器会尝试调整读取电压并重新读取，这增加了读取延迟。
- 强纠错 ：随着错误率的增加，需要更强的纠错码（ECC）来保证数据完整性，这也增加了处理延迟。
  这些因素共同导致了 SSD 的"慢速故障"（fail-slow）现象，即设备仍然可以工作，但性能显著下降。

### 2.2 现有解决方案的局限性

现有的解决方案主要包括：

- 温度感知技术 ：通过监控和调整 SSD 温度来减少错误率，但这只能部分缓解问题。
- 错误稀释技术 ：通过特殊的数据布局来减少错误的影响，但实现复杂且效果有限。
- 可靠性优先的 SSD 设计 ：牺牲一部分容量来提高可靠性，但这是静态的设计，无法适应设备的动态老化过程。
  这些方法都没有从根本上解决固定容量抽象带来的问题。

## 3. CVSS 系统设计

CVSS 系统包括三个主要组件：

1. 容量可变 SSD（CV-SSD） ：一种能够根据闪存块的老化程度动态调整可用容量的 SSD 设计。
2. 容量可变文件系统（CV-FS） ：能够适应底层存储设备容量变化的文件系统。
3. 容量可变管理器（CV-manager） ：协调 CV-SSD 和 CV-FS 之间的交互，管理容量变化过程。
   ![CVSS系统架构](d:\ReadingPaper\Paper_in_md\【CVSS SSD】【FAST24】\_The Design and Implementation of a Capacity-Variant Storage System.pdf-336e1707-a5b8-4780-adfa-a31512379088\images\d36f3878817f48a5c2bb074927e6c9d7c08381828ab8d8102c5add2a938377c7.jpg)

### 3.1 文件系统地址空间减少方法

为了实现在线地址空间减少，CVSS 考虑了三种可能的方法：

1. 非连续地址空间 ：允许文件系统的地址空间出现"空洞"，但这会导致地址空间碎片化和管理复杂性增加。
2. 数据重定位 ：将数据从要移除的地址空间移动到其他位置，但这需要大量的数据移动，增加了系统负担。
3. 地址重映射 ：保持物理数据不变，但更新逻辑到物理的映射关系，使某些物理区域不再可见。
   CVSS 选择了地址重映射方法，因为它具有以下优势：

- 无需移动数据，减少了系统开销
- 不会导致地址空间碎片化
- 实现相对简单

### 3.2 REMAP 命令工作流程

CVSS 引入了一个新的 NVMe 命令 REMAP ，用于实现地址重映射。当需要减少容量时，CV-manager 会发送 REMAP 命令给 CV-SSD，指定要重映射的逻辑地址范围。CV-SSD 接收到命令后，会更新其内部映射表，将指定范围内的逻辑地址重映射到新的物理位置，同时将老化严重的闪存块从活跃数据存储中排除。

![REMAP命令工作流程](d:\ReadingPaper\Paper_in_md\【CVSS SSD】【FAST24】\_The Design and Implementation of a Capacity-Variant Storage System.pdf-336e1707-a5b8-4780-adfa-a31512379088\images\18dcf93bf7eac85536b6bb109469e21c961d05316c543383415d37688ebbcb6a.jpg)

### 3.3 容量可变 SSD 设计

CV-SSD 的设计基于以下关键原则：
3.3.1 块管理
CV-SSD 将闪存块分为三类：

- 年轻块（Young Blocks） ：P/E 循环次数低，错误率低，性能好的块。
- 中年块（Middle-aged Blocks） ：P/E 循环次数中等，错误率和性能适中的块。
- 退休块（Retired Blocks） ：P/E 循环次数高，错误率高，性能差的块。
  随着 SSD 的使用，块会从年轻状态逐渐过渡到中年状态，最终到达退休状态。当块达到退休状态时，它们会被从活跃数据存储中排除，导致可用容量减少。
  3.3.2 生命周期管理
  CV-SSD 使用修改后的垃圾回收策略，考虑以下因素：

- 无效率（Invalidity Ratio） ：块中无效页面的比例。
- 老化率（Aging Ratio） ：块的 P/E 循环次数相对于阈值的比例。
- 读取率（Read Ratio） ：块被读取的频率。
  这些因素被组合成一个综合评分，用于决定垃圾回收的优先级。老化率高的块更容易被选中进行垃圾回收，从而加速它们的退休过程。
  3.3.3 降级模式
  当 SSD 检测到性能下降超过阈值时，会触发 CV_degraded 模式。在这种模式下，SSD 会主动减少可用容量，将老化严重的块从活跃数据存储中排除，以维持整体性能和可靠性。

![CV-SSD块管理](d:\ReadingPaper\Paper_in_md\【CVSS SSD】【FAST24】\_The Design and Implementation of a Capacity-Variant Storage System.pdf-336e1707-a5b8-4780-adfa-a31512379088\images\7141569befc0f4d6b17b629b51c897c77b46bb6af5b3f4c3b4a0d45cf8646731.jpg)

### 3.4 容量可变管理器

CV-manager 负责监控 CV-SSD 的状态，并在必要时触发容量减少。它执行以下任务：

1. 监控 SSD 老化状态 ：通过定期查询 SSD 的健康信息，包括 P/E 循环次数、读取重试次数和错误率等。
2. 决策容量减少 ：根据监控数据，决定何时减少容量以及减少多少。
3. 协调容量变化 ：与文件系统协调，确保容量减少不会导致数据丢失或系统不稳定。
   ![CV-manager设计](d:\ReadingPaper\Paper_in_md\【CVSS SSD】【FAST24】\_The Design and Implementation of a Capacity-Variant Storage System.pdf-336e1707-a5b8-4780-adfa-a31512379088\images\d7f9f633faac0991add383c995e6731c10498e5ebd636dbd726575460b373848.jpg)

### 3.5 容量可变文件系统

CV-FS 基于 F2FS（Flash-Friendly File System）实现，添加了对容量变化的支持。主要修改包括：

1. 地址空间管理 ：能够处理底层存储设备容量的动态变化。
2. 数据分配策略 ：优先将重要数据分配到年轻块，将不太重要的数据分配到中年块。
3. REMAP 命令支持 ：能够处理和响应 SSD 发送的 REMAP 命令。

## 4. 实现

### 4.1 CV-FS 实现

CV-FS 基于 Linux 内核 v5.15 中的 F2FS 实现，主要修改包括：

1. 块 I/O 层修改 ：添加对 REMAP 命令的支持，使文件系统能够处理底层设备的容量变化。
2. 超级块管理 ：修改超级块结构，添加对容量变化的跟踪和管理。
3. 空间分配策略 ：修改空间分配算法，考虑块的老化状态。

### 4.2 CV-SSD 实现

CV-SSD 基于 FEMU（Flash Emulator）实现，主要修改包括：

1. 块管理 ：实现年轻块、中年块和退休块的分类和管理。
2. 垃圾回收策略 ：修改垃圾回收算法，考虑块的老化状态。
3. REMAP 命令 ：实现 REMAP 命令的处理逻辑。
4. 错误模型 ：实现基于 P/E 循环次数的错误模型，模拟闪存单元老化的影响。
   错误模型使用以下公式：

$$E(c) = \alpha \cdot e^{\beta \cdot c}$$

其中，$E(c)$是错误率，$c$是 P/E 循环次数，$\alpha$和$\beta$是模型参数。

### 4.3 CV-manager 实现

CV-manager 作为用户空间守护进程实现，主要功能包括：

1. SSD 状态监控 ：通过 NVMe 命令查询 SSD 的健康信息。
2. 容量减少决策 ：基于预定义的策略决定何时减少容量以及减少多少。
3. REMAP 命令发送 ：向 SSD 发送 REMAP 命令，触发容量减少。

## 5. 实验评估

### 5.1 实验设置

实验环境配置如下：

- 处理器 ：Intel Xeon E5-2620 v3 @ 2.40GHz
- 内存 ：32GB DDR4
- 操作系统 ：Ubuntu 20.04 LTS，内核版本 5.15
- SSD 模拟器 ：FEMU，配置为 32GB 容量，8 个通道，8 个芯片/通道
- 工作负载 ：FIO（Flexible I/O Tester）、Filebench、Twitter traces
  比较对象包括：

- TrSS ：传统的固定容量 SSD
- AutoStream ：自动流管理的 SSD
- ttFlash ：使用尾延迟优化的 SSD

### 5.2 性能评估 5.2.1 读取性能

在 FIO Zipfian 和随机读取工作负载下，CVSS 相比 TrSS 提高了读取吞吐量：

- Zipfian 工作负载：提高了最多 2.1 倍
- 随机读取工作负载：提高了最多 1.8 倍
  ![读取性能比较](d:\ReadingPaper\Paper_in_md\【CVSS SSD】【FAST24】\_The Design and Implementation of a Capacity-Variant Storage System.pdf-336e1707-a5b8-4780-adfa-a31512379088\images\b3a9eb12177307e7550efcbf8d541716cb5070e9b6c740d77d4156bef4861868.jpg)
  5.2.2 写入性能
  在写入密集型工作负载下，CVSS 也表现出优势：

- 随机写入工作负载：提高了最多 1.5 倍的吞吐量
- 顺序写入工作负载：提高了最多 1.3 倍的吞吐量
  ![写入性能比较](d:\ReadingPaper\Paper_in_md\【CVSS SSD】【FAST24】\_The Design and Implementation of a Capacity-Variant Storage System.pdf-336e1707-a5b8-4780-adfa-a31512379088\images\83e855c0a6d7d99399496d2bd5d8da73fccef70461a9618c7bf0364c3150908b.jpg)
  5.2.3 Filebench 性能
  Filebench 测试结果显示，CVSS 在各种工作负载下都能显著降低平均延迟：

- Fileserver：降低了 43%的延迟
- Webserver：降低了 38%的延迟
- Varmail：降低了 45%的延迟
  ![Filebench性能比较](d:\ReadingPaper\Paper_in_md\【CVSS SSD】【FAST24】\_The Design and Implementation of a Capacity-Variant Storage System.pdf-336e1707-a5b8-4780-adfa-a31512379088\images\95d72909c83232f1650e96bf10e6375d970956566fa28635619585a7b4fbb46f.jpg)
  5.2.4 Twitter traces 性能
  使用 Twitter 的真实工作负载进行测试，CVSS 相比其他方法显著提高了吞吐量：

- 相比 TrSS：提高了最多 2.3 倍
- 相比 AutoStream：提高了最多 1.9 倍
- 相比 ttFlash：提高了最多 1.7 倍
  ![Twitter traces性能比较](d:\ReadingPaper\Paper_in_md\【CVSS SSD】【FAST24】\_The Design and Implementation of a Capacity-Variant Storage System.pdf-336e1707-a5b8-4780-adfa-a31512379088\images\ce06f591cc82b0450c4e7b9282c5e1eaa0e199a89e6f48b7bbb447c9b0d7fad3.jpg)

### 5.3 寿命延长

CVSS 能够显著延长 SSD 的使用寿命：

- 相比 TrSS：延长了最多 1.8 倍
- 相比 AutoStream：延长了最多 1.5 倍
  这主要是因为 CVSS 通过减少容量，避免了使用老化严重的闪存块，从而减少了错误率和读取重试次数。

![寿命延长比较](d:\ReadingPaper\Paper_in_md\【CVSS SSD】【FAST24】\_The Design and Implementation of a Capacity-Variant Storage System.pdf-336e1707-a5b8-4780-adfa-a31512379088\images\cdf224488ca491a33bae53f1a49f114957bb57414e99f71f318f13800d84dd2a.jpg)

### 5.4 敏感性分析 5.4.1 块退休阈值

实验测试了不同块退休阈值对性能和容量的影响。结果表明，较低的阈值会导致更多的块被退休，从而减少更多的容量，但能获得更好的性能。较高的阈值则相反，保留更多的容量但性能提升有限。

![块退休阈值敏感性分析](d:\ReadingPaper\Paper_in_md\【CVSS SSD】【FAST24】\_The Design and Implementation of a Capacity-Variant Storage System.pdf-336e1707-a5b8-4780-adfa-a31512379088\images\b74b207653bfecec4062610a5577053d8b0e64e95ee0c57ea5757f6c3c04a362.jpg)
5.4.2 ECC 强度
实验测试了不同 ECC 强度对性能和可靠性的影响。结果表明，更强的 ECC 能够减少不可恢复的错误，但会增加处理延迟。CVSS 通过减少容量，能够在使用较弱 ECC 的情况下也保持较高的可靠性。

![ECC强度敏感性分析](d:\ReadingPaper\Paper_in_md\【CVSS SSD】【FAST24】\_The Design and Implementation of a Capacity-Variant Storage System.pdf-336e1707-a5b8-4780-adfa-a31512379088\images\d3a757dfbf5be73be6a4a076f50a42cf19583ece8d1c19a6c944931452e71a1f.jpg)
5.4.3 垃圾回收公式权重
实验测试了垃圾回收公式中不同权重对性能和写入放大因子（WAF）的影响。结果表明，增加老化率的权重能够更快地退休老化块，从而提高性能，但可能会增加 WAF。

![垃圾回收公式权重敏感性分析](d:\ReadingPaper\Paper_in_md\【CVSS SSD】【FAST24】\_The Design and Implementation of a Capacity-Variant Storage System.pdf-336e1707-a5b8-4780-adfa-a31512379088\images\f91d4e8438e1375b0ff902f53771f90130375d0c82c0ec0a865c8f39d4151d74.jpg)

## 6. 容量可变性的应用场景

### 6.1 SSD 厂商

对于 SSD 厂商，容量可变性提供了以下好处：

- 简化设计 ：无需复杂的错误处理机制，可以通过减少容量来维持性能和可靠性。
- 性能/可靠性与容量的权衡 ：可以根据市场需求调整产品的性能、可靠性和容量特性。

### 6.2 数据中心

对于数据中心，容量可变性提供了以下好处：

- 自动排除不可靠块 ：系统会自动将老化严重的块从活跃数据存储中排除，减少数据丢失风险。
- 更容易的监控 ：可以通过容量变化直观地监控 SSD 的健康状态。
- 更长的更换间隔 ：通过牺牲一部分容量，可以延长 SSD 的使用寿命，减少更换频率。

### 6.3 桌面用户

对于桌面用户，容量可变性提供了以下好处：

- 延长 SSD 寿命 ：通过牺牲一部分不常用的存储空间，可以显著延长 SSD 的使用寿命。
- 降低成本 ：减少 SSD 更换频率，降低长期使用成本。

## 7. 与其他技术的兼容性

### 7.1 与 ZNS-SSD 的兼容性

CVSS 的容量可变性概念可以与区域命名空间（ZNS）SSD 结合，通过将老化区域从活跃数据存储中排除，进一步提高性能和可靠性。

### 7.2 与 RAID 系统的挑战

将容量可变性与 RAID 系统结合存在一些挑战，主要是因为 RAID 系统假设所有成员设备具有相同的容量。未来的工作将探索容量可变 RAID 的设计，使 RAID 系统能够适应成员设备的容量变化。

## 8. 结论

本文提出了容量可变存储系统（CVSS）的设计和实现，通过放松存储设备固定容量的抽象，实现了性能、可靠性和容量之间的动态权衡。实验结果表明，CVSS 能够显著提高性能、延长设备寿命并减少读取重试次数，为解决 SSD 老化问题提供了一种新的思路。

容量可变性的概念可以应用于各种存储场景，包括数据中心、桌面系统和嵌入式系统，为存储系统设计提供了新的维度。未来的工作将探索容量可变性与其他存储技术的结合，以及在更广泛的应用场景中的应用。
