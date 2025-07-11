<!--
 * @Author: lzq 1021578619@qq.com
 * @Date: 2025-07-08 15:44:17
 * @LastEditors: lzq 1021578619@qq.com
 * @LastEditTime: 2025-07-11 15:19:17
 * @FilePath: \ReadingPaper\Paper_in_CN\FDPVirt.md
 * @Description: 这是默认设置,请设置`customMade`, 打开koroFileHeader查看配置 进行设置: https://github.com/OBKoro1/koro1FileHeader/wiki/%E9%85%8D%E7%BD%AE
-->

> FDP ZNS 介绍：https://www.unionmem.com/news_detail-107-103.html

# FDPVirt：探究 FDP SSD 的行为特性

## 摘要

随着 SSD 在现代存储系统中的重要性不断提升，优化其性能和延长使用寿命的研究也日益深入。灵活数据放置（Flexible Data Placement，FDP）技术因其能够优化数据放置并减少垃圾回收（Garbage Collection，GC）开销而受到关注。本文介绍了 FDPVirt，一个基于 NVMeVirt 的 SSD 模拟器，专为探索 FDP 策略而设计。我们的评估表明，FDPVirt 能够精确复制 FDP 原型设备的 I/O 特性，并且通过细粒度数据放置策略将写入放大因子（Write Amplification Factor，WAF）降低了最多 26.3%，而动态调整回收单元（Reclaim Unit，RU）大小进一步将 WAF 降低了 8.3%。FDPVirt 提供了硬件受限 SSD 无法提供的见解，使其成为未来 SSD 优化研究的有价值工具。

## 1. 引言

随着 NVMe 存储设备的发展，优化性能和延长使用寿命仍然是关键挑战。其中一个主要问题是管理写入放大因子（WAF），它影响设备的耐久性和效率。灵活数据放置（FDP）技术作为一种有前景的解决方案，通过将数据与其预期寿命对齐，减少垃圾回收（GC）过程中的数据移动，从而提高 SSD 整体性能。然而，缺乏具有 FDP 功能的原型设备限制了学术研究。为解决这一问题，我们提出了 FDPVirt，一个基于 NVMeVirt 的 SSD 模拟器，旨在无需依赖真实硬件即可模拟和评估 FDP 策略。

本研究从多个方面检验 FDPVirt。首先，我们评估其复制 FDP 原型设备性能的能力，特别是在读/写延迟和 GC 行为等 I/O 特性方面。其次，我们探索细粒度数据放置策略如何影响写入放大因子（WAF）。

![FDPVirt的闪存转换层](d:\ReadingPaper\Paper_in_md\FDPVirt.pdf-84c42e32-85b9-404f-a7ea-5fcebacf5ff5\images\82b658730555e5c8af75381e1aa2d367b989c4e97a3381855bfa6663ce4cfca2.jpg)

研究表明，FDPVirt 可以将由不同热度级别的混合写入流组成的工作负载的 WAF 降低最多 26.3%。此外，我们还研究了 RU 大小对 WAF 的影响，发现它可以进一步将 WAF 降低 8.3%。这些发现证明 FDPVirt 为研究 FDP 策略和优化 SSD 性能与耐久性提供了一个多功能平台。

## 2. 设计与实现

FDP 要求将用户可通过回收单元（RU）区分的写入流放置到专用闪存存储地址。为满足这一要求，FDPVirt 扩展了 NVMeVirt 的闪存转换层（FTL），如图 1 所示。在图中，FTL 中的每一行（如 L0、L1 等）代表一个闪存块，对应 FDP 中的一个 RU。这些 RU 通过在 GC 期间启用独立回收，实现高效管理，从而减少 WAF。为实现 FDP，我们扩展了 FDPVirt 中的写指针（WP）系统。FDPVirt 不使用单一 WP，而是利用 WP 数组，每个 WP 指向特定 RU。这种设计使数据能够根据预期寿命分组，动态放置在多个 RU 中。FDPVirt 降低 WAF 的关键在于其细粒度数据放置，它最小化了 GC 期间长寿命数据的移动，从而减少内部写入，提高写入性能和设备耐久性。

此外，FDPVirt 通过 Units.Written 字段跟踪外部（主机驱动）和内部（GC 驱动）写入，如图 1 所示。该字段有助于计算 WAF，实现对 FDP 策略的精确评估。通过这些增强功能，FDPVirt 准确模拟了真实 FDP 启用的 SSD 行为，提供了一个平台来评估高级数据放置策略对性能的影响，特别是在 WAF 和延迟方面。

## 3. 评估

评估在配备 Intel i7-12700K 处理器（2.70 GHz，12 物理核心，20 逻辑核心）和 64GB DRAM 的系统上进行，运行 Linux 内核 6.5.0。作为比较，我们使用支持最多 8 个 RU 的 4TB PCIe Gen 5 兼容三星 FDP 原型 SSD。FDPVirt 配置了 2 个核心和 16GB 内存来处理用户 I/O 请求。我们使用微基准测试 FIO，通过自定义工作负载模拟各种真实世界 I/O 场景。

### 3.1 模拟 FDP 原型的性能特性

我们通过使用 FIO 测量从 4KB 到 128KB 的 I/O 大小的读写带宽，评估 FDPVirt 模拟性能的能力。

![不同I/O大小下真实设备与FDPVirt之间的性能相似性](d:\ReadingPaper\Paper_in_md\FDPVirt.pdf-84c42e32-85b9-404f-a7ea-5fcebacf5ff5\images\72cf5714cd95dd5168b7322653ea5b912ddd38ea4a531a47421a926964d95f96.jpg)

如图 2 所示，FDPVirt 与真实 FDP 设备之间的带宽差异平均为读取 11.1%，写入 4.1%。特别是，FDPVirt 在较大 I/O 大小下表现出更相似的性能。然而，在较小 I/O 大小下，差异增大，这是由于真实设备中的固件优化，如硬件驱动的 I/O 自动化减少了固件开销。这种优化加速了真实设备中的小 I/O。尽管如此，FDPVirt 仍然紧密模拟了 FDP 原型的性能，即使考虑到复杂的 SSD 优化。

![延迟和GC带宽相似性](d:\ReadingPaper\Paper_in_md\FDPVirt.pdf-84c42e32-85b9-404f-a7ea-5fcebacf5ff5\images\e515837aababbea0958b881fba3d590e7931b2be896e70196d8b0f71b754797b.jpg)

除了带宽外，我们还评估了 32 KiB 读写请求的延迟分布，比较 FDPVirt 与真实 FDP 原型 SSD。如图 3a 所示，两种设备的延迟分布非常相似，证明了 FDPVirt 在典型工作负载下模拟真实 FDP 设备行为的准确性。为评估 SSD GC 期间的模拟准确性，我们执行随机写入，然后进行预热（即用顺序写入填充整个设备空间）。如图 3b 所示，FDPVirt 和真实设备在 GC 期间经历类似的性能下降，FDPVirt 紧密复制了真实设备的行为，在初始下降后保持稳定性能。这进一步验证了 FDPVirt 在模拟真实条件下的有效性。

### 3.2 细粒度数据放置对 WAF 的影响

我们通过将 RU 数量从 1 增加到 16，研究 FDPVirt 上的数据放置策略如何影响写入放大。在此评估中，我们使用具有不同热度级别的混合工作负载。为生成不同热度，每个应用程序线程以不同速率向其专用 LBA 范围提交 I/O（即更高 I/O 速率，更热温度）。我们将具有相似热度的工作负载分组，并使每个组共享相同的 RU。通过这种方式将 RU 分配给应用程序线程，更多数量的 RU 会按热度诱导更细粒度的数据放置。由于需要主动触发 GC 来显示细粒度数据放置对 WAF 的影响，我们在提交具有不同热度的写入之前，顺序填充整个 SSD 空间。

![工作负载分布中随RU数量增加而减少的WAF](d:\ReadingPaper\Paper_in_md\FDPVirt.pdf-84c42e32-85b9-404f-a7ea-5fcebacf5ff5\images\8670bc6536974ecdd3bb8cb133825a9a9faf22c5336e2edbb523c181dc236b05.jpg)

如图 4 所示，增加 RU 数量导致 WAF 减少，观察到的改进高达 26.3%。这突显了对数据放置的细粒度控制显著降低了写入放大，特别是在具有各种热度级别的混合模式工作负载中，通过更有效地在 RU 之间分配数据。

### 3.3 RU 大小对 WAF 的影响

RU 大小在影响 WAF 方面起着关键作用。较小的 RU 在数据放置上提供更细的粒度，通过最小化内部数据移动和 GC 开销来减少 WAF。然而，真实设备通常具有固定的 RU 大小，这使得评估 RU 大小的影响变得具有挑战性。FDPVirt 在 RU 大小上提供灵活性（即用户可配置功能），使 WAF 的实证评估成为可能。我们的实验表明，将 RU 大小减半可将 WAF 降低 8.3%（即从 3.12 降至 2.86），这是由于更高效的垃圾回收和更好的数据热度对齐。相比之下，增加 RU 大小会将 WAF 提高到 4.48，表明较大的 RU 对多样化工作负载效果较差。虽然真实 FDP 设备由于 SSD 固件和硬件的封闭修改而在 RU 大小上缺乏灵活性，但 FDPVirt 提供了一个灵活平台来探索 RU 大小调整如何影响 WAF。这种灵活性为未来的 SSD 设计提供了宝贵见解，其中基于工作负载特性调整 RU 大小可以提高性能和耐久性。

## 4. 结论

本研究证明 FDPVirt 准确模拟了启用 FDP 的 SSD，复制了 I/O 特性、延迟分布和垃圾回收行为等关键方面。评估结果显示，FDPVirt 与真实 FDP 原型的性能紧密匹配，验证了其在真实条件下的有效性。通过启用细粒度数据放置策略和动态 RU 大小调整，FDPVirt 有效地将写入放大分别降低了最多 26.3%和 8.3%，提供了难以通过硬件受限 SSD 获得的宝贵见解。展望未来，后续工作将专注于集成更多 FDP 功能，并将 FDPVirt 应用于真实应用，进一步探索其在 SSD 优化方面的潜力。

## 参考文献

[1] NVMe 2.0 - TP 4146, FDP. https://nvmexpress.org/wpcontent/uploads/ NVM- Express- 2.0- RatifiedTPs_12152022. zip.

[2] J. Axboe. 2022. Flexible I/O Tester. https://github.com/axboe/fio.

[3] S. H. Kim, J. Shim, E. Lee, S. Jeong, I. Kang, and J. Kim. 2023. NVMeVirt: A Versatile Software- defined Virtual NVMe Device. In 21st USENIX Conference on File and Storage Technologies (FAST 23).