---
marp: true
---

# ZNS+

ZNS+: Advanced Zoned Namespace Interface for Supporting InStorage Zone Compaction(https://www.usenix.org/system/files/osdi21-han.pdf

https://blog.csdn.net/marlos/article/details/130234764

## Abstract

ZNS+: Advanced Zoned Namespace Interface for Supporting In-Storage Zone Compaction

-本文提出了一种名为ZNS+的新型支持LFS的ZNS接口及其实现，该接口允许主机将数据复制操作卸载到固态硬盘，以加快分段压缩。为此提出了两种文件系统技术：copyback感知块分配和混合分段回收。

-经实验，提出的 ZNS+ 存储系统的性能比基于 ZNS 的普通存储系统的性能好 1.33-2.91 倍。

## 1 Intro

段压缩：(也称为段清理或垃圾收集)

略

## 2 Backgroud

#### 2.1 SSD一些名词

parallel flash controllers (channels)

flash chips (ways)

chunk：由于现在的flash产品的flash页面大小通常大于逻辑块大小(例4 KB)，在本文中，我们将映射到flash页面的逻辑连续块称为chunk。（chunk指的是SSD中真实的一个page单元，但目前工艺已经大于4 KB了）

貌似这篇文章:chip = plane

一个memory chip通常支持：read, program, erase, and copyback 命令。

copyback指的是chip内的数据复制，单位是chunk。由于chip内的转移不能检查ECC，所以闪存控制器会在拷贝操作的同时检查错误。

#### 2.2 Zone Mapping

FBG(Flash Block Group)：一个zone映射到的一串物理块组。为了提高并行性，要放在不同的chip上，并行的chip数称为交错度（$D_{zone}$）。跨chip的连续块称为条带（stripe），以交错度为除数分成chip组（FCG），如下图：

Flash Chip Group,FCG

Flash Block Group,FBG

![image-20230828102735073](ZNS.assets/image-20230828102735073.png)

以上设计使得SSD只需要维护 Zone-FBG 映射。

一个zone的reset命令：分配新的FBG（更改对应的映射），写指针（WP）指向新的位置。等旧FBG擦除完可以给其他zone重新使用。

#### 2.3 F2FS 

>F2FS是Flash Friendly File System的简称。该文件系统是由韩国[三星](https://www.elecfans.com/tags/三星/)[电子](https://www.hqchip.com/ask/)公司于2012年研发，只提供给运行[Linux](https://www.elecfans.com/v/tag/538/)内核的系统使用，这种文件系统对于NAND闪存类存储介质是非常友好的。并且F2FS是专门为基于 NAND 的存储设备设计的新型开源 flash 文件系统。特别针对NAND 闪存存储介质做了友好设计。F2FS 于2012年12月进入Linux 3.8 内核。目前，F2FS仅支持Linux[操作系统](https://m.elecfans.com/v/tag/527/)。

F2FS：

- 包含6种类型的数据段（2M），同类段一次只能打开一个；//将冷热数据分割成不同的数据段，压缩时冷块会被放入冷段。

- 多头日志策略；//?

- 同时支持append logging，threaded logging。既可以严格顺序写， 也可以写入脏块的废弃空间。

- **日志写入自适应**：如果空闲段足够多，优先追加写入；空闲段不足，将数据写入dirty segment的无效块上。然而， 实际上后者在ZNS中是被禁用的，所以F2FS for ZNS会经常触发压缩。

- 前后台压缩机制：空间不足，先前台压缩（造成少量IO延迟）；闲时后台压缩（无法及时回收，尤其是在空间占用高，突发写请求时）

  本文主要关注前台压缩的性能

![image-20230829135007905](ZNS.assets/image-20230829135007905.png)

## 3 ZNS+ Interface and File System Support

### 3.1 动机

**普通的端压缩**

朴素的LFS端压缩包括四个步骤：

1. 受害者段（victim segment）选择
2. 目标块分配
3. 有效数据复制
4. 元数据更新

![image-20230829143324993](ZNS.assets/image-20230829143324993.png)

其中，SSD的空闲间隔很长（idle）

read phase、write phase、metadata update ~？？

**基于IZC的段压缩方案**

![image-20230829160053722](ZNS.assets/image-20230829160053722.png)

引入了copy offloading操作，sends zone_compaction commands to transfer the block copy information 

### 3.2 LFS-aware ZNS+ Interface

三个新命令：zone_compaction, TL_open, and identify_mapping.

zone_compaction用于请求IZC操作（区内压缩）：现有的simple copy命令要求目标地址单一、连续；ZNS+下，可以指定多个目标LBAs

TL_open：打开区域，准备threaded logging。接下来这个区域可以不经reset就覆写。

identify_mapping：主机使用这个命令确定各个chunk所在的flash chip

##### 3.2.1 IZC(Internal Zone Compaction)

ZNS+的压缩流程：

###### （1）Cached Page Handling：

检查victim段各个可用块对应的page是否被主机DRAMcache。If Cacheed page dirty：必须被写入目的段，并排除在IZC操作外；If clean：既可以通过写请求从主机传输写入，也可以从SSD内部复制。

//ZNS一般使用TLCorQLC，内部复制没有主机来得快。然而，最新的ZNAND有极短的读延迟，对于ZNAND SSD，in-storage copy也可能更快。

###### （2）Copy Offloading：

zone_compaction(sourceLBAs, destination LBAs)

###### （3）处理 IZC

ZNS+ SSD处理压缩指令，其中定义了copybackable chunks（如果其中所有块都是复制来的）。其他不可回拷的正常读写。

**异步**

zone_compaction请求的处理是异步的，主机请求进入请求队列后不会等待命令完成。LFS有自己的checkpoint，异步不会影响文件系统一致性。

ZNS+对后续的普通请求重新排序，避免zone compaction操作的长延迟的影响：放行与压缩地址无关的普通请求；甚至包括对正在压缩的区域的读请求，如果写指针WP已经经过了要读取的目标块地址，那么也可以放行。

##### 3.2.2 Sparse Sequential Overwrite 

**Ineternal Plugging**

为了支持 F2FS的threaded logging，ZNS+需要做少量顺序覆写。

尽管二者有冲突，但是：threaded logging访问的脏段的块地址的闲置空间时，也是从低地址端向高地址端的，虽然不连续但是也递增。因此说他的访问模式是 Sparse Sequential Overwrite （即——WP不减小）

如果固态硬盘固件读取请求之间跳过的数据块，并将其合并到主机发送的数据块中。那就变成了密集的连续写入请求——这种技术被称为internal Plugging。

![image-20230829172811964](ZNS.assets/image-20230829172811964.png)



上图是一个Plugging操作的例子：chunk0中的AB，是有效块（跳过块），PQ是无效块，需要回收。

**Opening Zone for Threaded Logging** 

SSD必须知道目标段的跳过块：通过对比写请求首个LBA和当前WP（维护的是上次写的位置？），SSD确定哪些是跳过块。然而，必须要等到写请求到达才能确定跳过块，产生了延迟。

因此，增加了TL_open这个特殊命令，TL_open(openzones, valid bitmap)。它会提前发送一个bitmap，SSD可以在thread logging的写请求到达之前确定那些块要跳过。

**LogFBG Allocation**

原有的被"TL_opened"的zone要被重写，新分配一个FBG叫LogFBG（图中， original FBG (FBG 6) and the LogFBG (FBG 15)）

由于静态映射机制，这个新分配的LogFBG也是在同一个chip上的，所以可以使用copyback快速完成；TL_opened的区域最终关闭时，LogFBG替换了原始的FBG，原始LGB被释放以供重用。



//以上内容应该对应图中的chip0的情况。

![image-20230829172811964](ZNS.assets/image-20230829172811964.png)

**LBA-ordered plugging**

按地址有序插入，如图中2-p、3-p、4-p的情况。

**PPA-ordered plugging**

比如说chunk3可以在chun0、chunk2中的写请求到来之前就进行复制。

physical page address (PPA)   即只考虑物理地址的顺序写入约束。可以检查并让后续的完整chunk提前copy。

但是，过多提前的plug会干扰用户IO请求，所以只有目标chip空闲时才会进行。

**为什么Threaded Logging能提升性能**

二者copy的块的数量是相同的。但是，threaded logging减少了重定位时元数据的修改（?）；调用空闲的chip，internal plug的开销部分隐藏了；最小化写入请求的平均延迟



### 3.3 ZNS+-aware LFS Optimization

#### 3.3.1 copyback-aware的块分配机制

**现有LFS未充分利用copyback：**

![image-20230831170443421](./ZNS.assets/image-20230831170443421.png)



对于identify_mapping 命令，ZNS+SSD会返回FCG ID和chip ID

#### 3.3.2 混合式段回收

虽然threaded logging减少了回收开销，但其效率依然低于端压缩，两大原因：

**回收成本不均衡**

段压缩可以直接选取压缩成本最低的受害者段（例如，选有效数据最少的）。但threaded logging只能从同类型的脏数据段中为某写入请求选择目标数据段，以防止不同类型的数据混杂在一个数据段中。

**预失效块问题**

如果长时间使用稀疏到的线性日志写而不进行检查点处理，它的回收效率将进一步下降:
这是由于某些块虽已经失效，但仍被存储元数据引用，因此不可回收。当一个逻辑块被文件系统操作作废，但新的检查点仍未记录时，该逻辑块就会成为预作废块(预失效块)，不得覆盖，因为崩溃恢复需要恢复它。

预无效块会随着threaded logging的继续而累积，而它们可以通过段压缩来回收，因为段压缩伴随着检查点更新。

***

**定期检查点**
为了解决预无效块问题，我们使用定期检查点，每当累积的预无效块达到一定数量，触发检查点。这需要文件系统进行监测，元数据块上的写入流量就会增加，如果过于频繁地调用检查点，固态硬盘的闪存耐用性就会受到损害。因此需要一个合适的阈值——128 MB
**回收成本模型**
我们提出了混合段回收（HSR）技术，通过比较线程日志和段压缩的回收成本来选择回收策略。
Threaded Logging 的开销：
$$C_{TL} = f_{plugging}(N_{pre-inv}+N_{valid})$$

段压缩的开销：
$$C_{SC} = f_{copy}(N_{valid})+ f_{write}(N_{node}+N_{meta}) - B_{cold}$$

B_cold 表示冷数据块迁移的未来预测收益。

(感觉这部分有点随意)

## 4 实验

**一些配置信息：**
模拟器：基于FEMU 
2 GB of DRAM, 16 GB of NVMe SSD for user workloads, and a 128 GB disk for the OS image 
Host interface: PCIe Gen2 2x lanes (max B/W: 1.2 GB/s)
SSD： 默认存储介质是MLC,  The data transmission
默认的ZNS+ SSD zone size=32 MB, 包含16 flash blocks分布在16 flash chips.
（注：The copyback operation is approximately 6–10% faster than the normal copy operation）
**两种不同版本的ZNS+**
IZC：不包含threaded logging
ZNS+： 混合式

### 段压缩表现：

ZNS与IZC在不同负载下的段压缩表现（模拟器）

![image-20230913060105924](image-20230913060105924.png)

与 ZNS 相比，IZC 通过移除主机级复制，将区域压缩时间减少了约 28.2%- 51.7%。IZC存储内复制操作减轻了用户 IO 请求对主机资源和主机到设备 DMA 总线的干扰。但IZC技术增加了检查点延迟。

### threaded logging

in-storage zone compaction 与 threaded logging 下的效果
注： IZC(w/o cpbk) 和 ZNS+(w/o cpbk)即禁用回拷的版本

![image-20230913061344093](./ZNS.assets/image-20230913061344093.png)

***

##### 元数据开销对比：

![image-20230913061910497](./ZNS.assets/image-20230913061910497.png)

***

##### 性能对比、WAF

(ZNS的WAF呢？)
![image-20230913062424226](./ZNS.assets/image-20230913062424226.png)



### 在真实SSD上的性能表现

![image-20230913062808434](./ZNS.assets/image-20230913062808434.png)



















## ZNS SSD的结构

> Zoned Namespace (ZNS) SSD 
>
> https://blog.csdn.net/Z_Stand/article/details/120933188

粗粒度单位——zone，每个zone管理一段LBA（Logic block adr），只允许顺序写，可以随即读；如果想覆盖写，就要reset整段LBA

End-To-End？绕过I/O stack（内核文件系统，驱动等等），通过Zenfs直接与ZNS-SSD交互

> ZNS+: Advanced Zoned Namespace Interface for Supporting InStorage Zone Compaction(https://www.usenix.org/system/files/osdi21-han.pdf)
>
> https://blog.csdn.net/marlos/article/details/130234764

<img src="ZNS.assets/image-20230808174737502.png" alt="image-20230808174737502" style="zoom:110%;" />



Flash Chip Group,FCG

Flash Block Group,FBG





















## SSD 各层级



![img](ZNS.assets/v2-bff1882898e377ce9ed29911fcea4a0d_b.jpg)



https://zhuanlan.zhihu.com/p/26944064

![image-20230807135849852](./ZNS.assets/image-20230807135849852.png)





1. DIE/LUN是接收和执行闪存命令的基本单元
   但在一个LUN当中，一次只能独立执行一个命令，你不能对其中某个Page写的同时，又对其他Page进行读访问。

2. 每个Plane都有自己独立的Cache Register和Page Register，其大小等于一个Page的大小。

3. Multi-Plane（或者Dual-Plane），主控先把数据写入第一个Plane的Cache Register当中，数据保持在那里，并不立即写入闪存介质，等主控把同一个LUN上的另外一个或者几个Plane上的数据传输到相应的Cache Register当中，再统一写入闪存介质。

4. 闪存的擦除是以Block为单位的
   那是因为在组织结构上，一个Block当中的所有存储单元是共用一个衬底的（Substrate）



**Read Disturb 读干扰**
读干扰影响的是同一个block中的其他page，而非读取的闪存页本身。
当你读取一个闪存页（Page）的时候，闪存块当中未被选取的闪存页的控制极都会加一个正电压，以保证未被选中的MOS管是导通的。这样问题就来了，频繁地在一个MOS管控制极加正电压，就可能导致电子被吸进浮栅极，形成轻微写，从而最终导致比特翻转
**Program Disturb 写干扰**
轻微写导致的，既影响当前的page也影响同一个block的其他page。
**存储单元之间的耦合**
导体之间的耦合电容

一个存储单元存储1bit数据的闪存，我们叫它为SLC（Single Level Cell），存储2bit数据的闪存为MLC（Multiple Level Cell），存储3bit数据的闪存为TLC（Triple Level Cell），如表3-1所示。


![在这里插入图片描述](ZNS.assets/2021050713384842.jpg)



>F2FS文件系统

三星开源，但是没有什么应用

https://blog.csdn.net/weixin_39886929/article/details/111679671



https://blog.csdn.net/weixin_44465434/article/details/113374562

EROFS







# eZNS: 

### An Elastic Zoned Namespace for Commodity ZNS **SSDs**

https://www.usenix.org/system/files/osdi23-min.pdf

## 0 Abstract

新兴的分区命名空间（ZNS）固态硬盘提供了粗粒度的分区抽象，有望显著提高未来存储基础设施的成本效益，并降低性能的不可预测性。（作者对ZNS的总结评价）

现有的ZNS SSDs 采用静态分区接口（zoned interface），它们无法适应工作负载的运行时行为；无法根据底层硬件能力进行扩展；共用区域相互干扰。

eZNS——这是一个弹性分区命名空间接口，可提供性能可预测的自适应分区，主要包含两个组件：

- zone arbiter，区域仲裁器，负责管理Zone的分配和激活plane里的资源。

- I/O scheduler，分层I/O调度器，具有读取拥塞控制和写入接纳控制。


eZNS实现了对ZNS SSD的透明使用，并弥合了应用程序要求和区域接口属性之间的差距。在 RocksDB 上进行的评估表明，eZNS 在吞吐量和尾部延迟方面分别比静态分区接口高出 17.7% 和 80.3%（at most）

## 1 intro

通过划分为Zone ，实现“从设备端隐式垃圾收集 (GC) 迁移到主机端显式回收” ，消除了随机写，解决写放大（WAF）问题。

要在ZNS上构建高效的I/O stack，我们应该了解：

1. 底层固态盘如何暴露接口并强制实现它的限制（怎么顺序写？）
2. 设备内部机制如何权衡成本与性能。（代价是什么？）

文章详细调研了一款ZNS产品，在zone striping, zone alloation, and zone
interference三个方面进行对比分析。旨在了解商用 ZNS 固态硬盘的特性。

提出eZNS，新的接口层，它为主机系统提供了一个与设备无关的分区命名空间。

- 减少了区域内/外的干扰（？）
- 改善了设备带宽（通过分配激活资源，基于应用优化的负载配置）

***

eZNS对上层应用和存储栈透明，包含两个组件：

- **区域仲裁器**

维护 “设备影子视图” （device shadow view，该视图本质上是SSD的虚拟表示，仲裁者使用它来跟踪当前正在使用哪些区域以及哪些区域可供分配。）

基于该视图来实现 “动态资源分配” 策略，这意味着它可以根据当前的工作量和其他因素调整分配给每个区域的资源量。

- **分层 I/O 调度器**

充分利用ZNS SSD没有硬件隐藏信息的特性，读取 I/O 的可预测性变得更强，可以直接利用这一特性来检查区域间的干扰。

此外，由于固态存在写入缓存，所有应用的写入操作共享一个性能域，所有zone都激活的时候会堵塞。因此对读进行本地拥塞控制，对写入全局准入控制。



## 2 背景&动机

#### 2.2 Zoned Namespace SSDs

namespace：类似硬盘的分区，但是被NVMe设备主控管理（而不是OS）

zone：多个blcok的集合

ZNS能为主机应用提供可控的垃圾回收；消除了设备内部I/O行为（主要指消除写放大）

三种命令：read, sequential write, and append.

**与上一篇文章有出入的地方：**与普通写入相比，区域追加命令不会在 I/O 提交请求中指定 LBA，而固态硬盘会在处理时确定 LBA 并在响应中返回地址。

因此，用户应用程序可以同时提交多个未完成操作，而不会违反顺序写入的限制。

#### 2.3 Small-zone and Large-zone ZNS SSDs

*physical zone*：最小的区分配单元，由同一个die上的一个或多个块组成。

*logical zone*：由多个物理区组成的条带区域

**区域划分大小的影响：**

*Small zone ZNS SSD*：提供粗粒度的大型逻辑区域，采用固定的条带化配置，跨越所有内部通道的多个die，不灵活，适用于zone需求少的情况。

*Large zone ZNS SSD*：每个区域都包含在单个die中，最小为一个擦除块。灵活，同时可激活的资源更多。最近有研究认为越小越好，可以减少区回收延迟造成的干扰，所以这个区域划分有待探究。

#### 2.4 The Problem: Lack of an Elastic Interface

ZNS SSDs带来的问题：在zone被分配、初始化之后，他的性能就已经固定了

1. 分区的性能只取决于分区位置的放置和stripe的配置。（但我们希望它的性能符合应用的需求）虽然，用户定义的逻辑分区已经带来了灵活性，但是应用不了解正在共享设备的其他应用的状态。目前，只能实现“次优”的性能表现。
2. 现有的接口不能适应负载的变化。专门开发一个应用来捕获I/O执行时的数据是不现实的。用户使用时，不得不以最坏的情况来配置分区。（over-provision）
3. 共用一块位置的区域互相影响，尤其当固态硬盘被过度占用时，其性能会按比例下降。



## 3 ZNS SSD的性能

(用测试说明现有的ZNS太固化，不灵活)

#### **3.1 Set up**

>SPDK

本文使用在 SPDK 框架上运行的 Fio 基准测试工具来生成合成工作负载。作者在 SPDK 中添加了一个薄层，以实现逻辑区域概念并实现不同的区域配置。

- 写入负载默认为单个逻辑区域上的顺序访问
- 读取负载默认为随即访问

![image-20230926214021627](image-20230926214021627.png)

#### **3.2 System Model**

<img src="ZNS.assets/image-20230807161309156.png" alt="image-20230807161309156" style="zoom:67%;" />

一个tenant=某个存储应用；它拥有一个或多个namespece；其中包含逻辑区域；一个逻辑区包含了多个物理区；物理区下面管理通道、die

/* 应用与NVME驱动之间存在一个 zoned block device (ZBD) layer

1. 在命名空间/逻辑区域管理方面与应用程序互动管理；
2. 考虑到应用需求，协调逻辑区到物理区的映射
3. 安排 I/O 序列，大限度地提高设备利用率并避免行头阻塞。*/

#### 3.3 Zone Striping

区域条带化是一种用于实现更高吞吐量的技术，尤其是大型 I/O。包含参数：

1. 条带大小：条带中最小的数据放置单位。 
2. 条带宽度：定义了同时激活的物理区域数量并控制写入带宽。

观察：当条带大小（stripe size）与 NAND 操作单元（这里是16KB）相匹配时，可以实现较好分条效率。

![image-20231004051937708](ZNS.assets/image-20231004051937708.png)

**Challenge #1: Application-agnostic   Striping**

stripe 最好与用户I/O匹配，太小了影响设备I/O效率，太大了浪费性能（单个zone性能变好了，但是可并行的zone总数低，影响其他应用）

（但是搞来搞去还是在等于pagesize时最好，动态调整的点在stripe width上）

#### 3.4 Zone Allocation and Placement

现有分配机制：找到下一个可用die，在这个die内根据磨损均衡等各种策略选择最好的块

图5：stripe size = 16KB，每个逻辑区包含N个物理区（横坐标）

![image-20231004035828330](ZNS.assets/image-20231004035828330.png)

图5中 由上至下分析

1. PCIe gen3带宽跑满了
2. 应用发出的请求不足，因为请求队列深度只有1。(1,2对比可以体现出QD的差异)
3. 每个物理芯片80MB/s的读取和40MB/s的带宽，需要更多的物理区域(大约40~80)来充分利用通道或PCIe带宽（这部分做的很迷惑？）

**Challenge #2: Device-agnostic Placement**

理想的分配过程应该向应用充分利用ZNS SSD的所有内部I/O并行性。现有分配机制完全不考虑应用程序先前的分配历史，以及应用之间的交互关系，这会导致不平衡的区域放置，损害I/O并行性，并危及性能。

两种类型的低效放置：

- Channel-overlapped placement
- Die-overlapped placement

Observation：

在不知道设备内部规格的情况下推断区域的物理位置很困难的，我们需要建立一个设备抽象层

(1)依赖于设备的一般分配模型;
(2)维护底层物理设备的阴影视图;
(3)分析其在不同物理通道和模具上的放置平衡水平

#### 3.5 I/O Execution under ZNS SSDs

/* 当读取拥塞时，观察到die/channel争用下的延迟峰值。这是因为 ZNS SSD 没有任何物理资源分区。在namespace内或namespace之间，干扰都会比传统固态硬盘更严重。（感觉ZNS分配更混乱？因为跨物理区的分配？）*/

与物理配置的SSD作对比，128 Zone 16KB stripe size, 70% filled：（可以看到传统SSD因为垃圾回收损失之大）

![image-20230816064000631](ZNS.assets/image-20230816064000631.png)

**Challenge #3: Tenant-agnostic Scheduling**

无论部署的工作负载如何，现有的ZNS ssd分区接口对域间情况提供的性能隔离和公平性保证很少。
人们不能忽视在一个die上的读干扰，因为

(1)任意数量的区域可以在die上碰撞，

(2)单个die的带宽很差，因此即使在设备上非常低的负载下，干扰也会变得严重，

(3)它会导致严重的线路阻塞问题并降低逻辑区域的性能。

Observation:

在多租户场景中使用ZNS ssd时，首先应该了解不同的命名空间和逻辑区域如何共享底层设备的通道和NAND die，将它们的关系划分为竞争和合作类型，并在区域间场景中采用拥塞避免方案以实现公平性。
由于没有设备簿记操作，因此I/O延迟表示碰撞死亡上的拥塞级别。
此外，写缓存拥塞需要全局解决。因此，一个可能的解决方案：

(1)一个全局中心仲裁器，决定所有活动区域之间的带宽共享;
(2)基于拥塞级别编排读I/O提交的perzone I/O调度器。



总结一下，三个挑战：

1. 条带化参数配置与应用无关
2. 区域放置与硬件无关
3. 调度与租户无关

## 4  eZNS

#### 4.1 Overview

eZNS停留在NVMe驱动程序之上，并提供原始块访问。

实现一个新的弹性的分区接口v-zone以解决上述问题 

![image-20231004061709847](ZNS.assets/image-20231004061709847.png)

**区域仲裁器：**

(1)在硬件抽象层(HAL)中维护设备影子视图，并为区域分配和IO调度提供基础;

(2)执行序列化的区域分配，避免重叠放置; (就是把每个stripe unit分摊到不同的die上)

(3)通过收获机制动态缩放区域硬件资源和I/O配置。

**I/O调度器：**

一种延迟调度机制

一种基于令牌的准入机制

#### 4.2 HAL

约束条件：

- 物理区域由同一个die上的多个可擦除块组成
- ZNS在die上均匀地分配物理区（规定活动区数必须是die总数的倍数等）
- 分配机制遵循磨损均衡需要。连续分配区域不会在一个die上重叠，直至已经遍历所有die（最后一个contract不那么绝对）

eZNS维护一个影子设备视图（我们的机制不需要认识到SSD NAND芯片和通道的二维几何物理视图，也不需要维护精确的区域-芯片映射），暴露区域分配和I/O调度的近似数据位置。
我们的机制只依赖于来自设备规格的三个硬件参数：

**MAR** ，maximum active resources 通常与die数成正比，通过离线校准实验测试得到

**NAND page size** （ for striping ）不成文的标准，例如TLC一般用16KB。stripe size选用page size的倍数。

**physical zone size** 用以构造条带组和逻辑分区

#### 4.3 连续区域分配器

eZNS开发了一个简单的区域分配器，尽可能减少die冲突，具体地：

分配器把每个逻辑区请求缓存进一个队列。由于open命令完成时不能保证物理die已经分配完成，因此在区域打开期间，实现了一个保留机制：刷新一个数据块，强制将一个die绑定到该区域。这样能让写操作立即完成（即使高负载情况下，设备的写缓存也会接收一个块）。

为了加快这个过程， 主动地维护一定数量的块用作保留区。分配完成后，更新分配记录，写入元数据块。

以上的最终目的是避免打开多个逻辑区域时的交错分配，减轻重叠。

#### 4.4 Zone Ballooning

v-zone：一种特殊的逻辑分区，能自动扩展资源，以轻量级的方式匹配不断变化的应用程序需求。

![image-20230816193101212](ZNS.assets/image-20230816193101212.png)

与静态逻辑zone类似，v-zone包含固定数量的物理zone。但与静态逻辑分区不同，它将物理区域划分为一个或多个条带组。当第一次打开v-zone或到达上一个条带组的终点时，它会分配一个新的条带组。当写指针到达前一个分条组的末端时，前一个分条组中的所有物理分区都必须完成。（以stripe group为管理单元）

分条组中物理分区的个数在分配时根据“local overdrive“机制确定，实现分区的灵活分条。

v-zone可以：

1. 在其他命名空间处于低活动资源使用状态时，通过从其他命名空间租用备用空间来扩展其条带宽度;
2. 当它完成I/O、通过写到分条组末尾或显式终止时，返回它们

**初始化：**

具体地，所有可用物理空间被划分为两类：基本分区（$N_{essential}$）、备用分区（$N_{spare}$）。基本分区包含能最大化写入带宽的激活物理分区。

均匀分配：例如，假设ZNS SSD现有$N$个namespace，那它只能独占并激活$N_{essential}/（N*MAR）$个物理区。

**Local Overdrive**：

eZNS 使用“Local Overdrive”操作通过从其命名空间的备用组重新分配备用磁盘空间来增强其写入 I/O 能力。 

该机制估算命名空间内的资源使用情况，检查剩余的备用磁盘，并根据写入活动和打开的 v-zone 数量调整分配给每个 v-zone 的备用磁盘数量。

**Global Overdrive**：

它是根据整个SSD的写入强度触发的。根据非活动命名空间的分配历史进行识别，让备用空间在活动命名空间之间分配。

当备用空间要被原namespace使用时，有一个回召机制。

总结，通过仲裁器和Overdrive操作提高了驱动器的整体性能和效率。

#### 4.5 I/O调度

**Goal：**

旨在在 v -zone 之间提供平等的读/写带宽份额，最大限度地提高设备利用率并缓解队头阻塞。

写：采用基于延迟测量的拥塞控制机制：ezNS 中具有缓存感知能力的写入准入控制，监控写入延迟来调整拥塞窗口大小（1-4 stripe width）

读：并使用基于令牌的准入控制方案来调节写入。它定期生成令牌并允许分批写入 I/O 。

-  eZNS 中的读取调度器和写入准入控制几乎不需要协调，并且使用延迟作为信号来推断带宽容量。
-  当在物理芯片上混合读写I/O时，总聚带宽可能会因NAND干扰而下降，但eZNS可以在没有显著协调的情况下处理这个问题。(?) 
-  用户 I/O 中同一物理区域的条带会合并并作为一个写入 I/O 批量提交，因此较小的条带大小不会降低写入带宽。



### 测试

**Default v-zone Configuration**

4 Namespaces (Each namespace has 64 Active zones)

Each Namespace

- Essential resources :32 (128 / 4) 
- Spare resources :32 (64 - 32)
- Maximum active v-zones :16
- Minimum stripe width : 2 with 32KB stripe size (32 / 16)
- Physical Zones in Logical Zone :16

结合之前的实际硬件参数：

![image-20231004074250020](ZNS.assets/image-20231004074250020.png)



证明 Local Overdrive是有效的

![image-20231004074852711](ZNS.assets/image-20231004074852711.png)

![image-20231004074816719](ZNS.assets/image-20231004074816719.png)



Global Overdrive

NS1 NS2 NS3 两写入， NS4 八写入任务。NS1、NS2 和 NS3 在 t=30 秒时停止写入，并在 t=80 秒时恢复写入活动。当其他三个区域闲置时，来自 NS4 的 v 区域使用全局超速原语从其他命名空间获取多达 3 倍的备用区域，并最大限度地利用其写入带宽（2.3GB/s）。然后，当其他区域再次开始发出写入指令时，它可以迅速释放收获的区域。

![image-20231004075129734](ZNS.assets/image-20231004075129734.png)



A B都是覆写, CD同时执行随机读。

在RocksDB上，eZNS 相较于 static zoned interface 提升了 17.7% 的吞吐量和 80.3% 的尾时延。

![img](ZNS.assets/v2-25511ef9edebdbccdb9edc4b906a31de_1440w.webp)

## 总结

具体而言，ZNS SSD接口的**静态**和**不灵活**体现在三个方面：

**1. Zone Striping：**不同workloads在不同的stripe size和stripe width设置下表现不同

**2. Zone Allocation：**一个logical zone中physical zones越多，性能越好；zone放置时的channel overlap和die overlap都会影响并行度。现有zone放置机制没有考虑这些特性。

**3. Zone Interference：**ZNS内部执行I/O请求、其他用户执行的I/O请求都会互相影响。现有机制任务间隔离性差。

它有两个组件：

- **Zone 仲裁者（Arbiter）**：维护 device shadow view，执行 zone 分配以避免 overlap （解决问题2），通过 zone ballooning 执行动态资源分配 （解决问题1）
- **Zone I/O调度器**：使用**局部拥塞控制机制 (congestion control)** 来调度读请求；使用**全局权限控制机制 (admission control)** 来调度写请求（解决问题3）





> ZenFS——RocksDB on ZNS device
>
> https://zhuanlan.zhihu.com/p/555476626

一个韩国人讲eZNS

https://www.youtube.com/watch?v=q10_ExFD8RA



# ZNSwap

ZNSwap: un-Block your Swap

https://www.usenix.org/system/files/atc22-bergman.pdf

主机端OS内实现垃圾回收机制

## 1 Intro

固态硬盘上的交换不再被视为最后的内存溢出机制，而是有效回收内存和提高系统效率的关键系统组件。但固态硬盘未被作为交换设备广泛应用，其中一个关键限制是：

随着固态硬盘使用率的增加，系统性能会下降，如图。

<img src="ZNS.assets/image-20231114102732571.png" alt="image-20231114102732571" style="zoom:67%;" />

这些性能异常现象没有简单的解决方案——它们源于块接口抽象与闪存介质的内在不匹配。

---

ZNSwap为SSD空间回收提供了一种新颖的、空间高效的主机端机制，我们称之为ZNS Garbage Collector(ZNGC)

与传统固态硬盘的设备侧 GC 不同，ZNGC 与操作系统紧密集成，可直接访问操作系统的数据结构，并利用这些数据结构优化其运行。

然而，问题：空间回收过程自然涉及到设备上逻辑块的迁移，而未与拥有数据的应用程序协调块位置的变化。

这在 SSD 端做 GC 时不是问题，因为用户可见的LBA（逻辑块地址）保持不变。但把设备侧的方案应用于主机侧 ZNGC 会带来不可接受的空间开销，因为在 TB 级设备中，每个 4KiB 块都需要维护反向映射...

>关于上述这个问题：映射表不可以放到主存中吗？ 1TB 级SSD设备也不会把整张页表都存储在DRAM中，因为根本没有这么大的板载DRAM（1 TB Flash needs 1GB DRAM）并且使用很大的DRAM空间是要考虑断电时的落盘速度的 ；（存疑）SSD应该是只加载一小部分映射表到DRAM，其余存在Flash中，类似CPU-主存中的TLB。

ZNSwap 通过将反向映射信息存储到逻辑块元数据中，与被交换的页面内容一起写入，从而避免了主机的这些开销。确保映射在页面生命周期内正确无误。

---

具体地，带来了如下好处：

- 细粒度的空间管理：ZNSwap 可省去 TRIM 命令，实现更高的性能和更好的空间利用率。
- 动态的ZNGC优化：ZNSwap 可动态调整同时存储在交换设备中的交换入页的数量，从而提高多读和读写混合工作负载的性能。操作系统会在交换设备中保存一份未修改的已交换内存页副本以避免这些页面的交换惩罚。此类页面可能占用的磁盘空间由操作系统设置静态上限（Linux 为 50%，不可配置）。然而，这一静态阈值并不适合所有工作负载：较低的阈值会降低以读取为主的工作负载的性能，而较高的阈值则会影响读写混合型工作负载（第 3.1.2 节）。ZNSwap 可监控 WAF，并在必要时通过回收交换页面的 SSD 空间来降低存储占用率。
- 灵活的数据放置和空间回收策略：ZNSwap 允许轻松定制磁盘空间管理策略，使 GC 逻辑符合特定系统的交换要求。例如，策略可以强制将生命周期相近的数据集中到同一区域，这在以前的文献[28, 34, 44, 56]中被证明是有用的；也可以通过专用于处理来自特定租户的交换的单独区域来实现更好的性能隔离。
- 准确的多租户计费：当ZNGC在主机上运行时，zswswap与cgroup计费机制集成，显式地将GC开销归因于不同的租户，从而提高了它们之间的性能隔离。

>TRIM：粗糙地理解一下TRIM指令，操作系统使用TRIMs提示块SSD来释放特定的LBAs，从而减少SSD端GC的负载。在OS执行Swap时，大多禁止使用TRIM，开销比较大

综上所述，主要贡献如下:

- 深入分析传统块ssd用作交换设备时的缺点。
- 一种新机制，通过利用逻辑块元数据进行有效的反向映射，使ZNS ssd能够用于交换，而无需在主机中使用资源昂贵的重定向机制。
- 自定义交换感知SSD存储管理策略，减少WA，提高性能，并在多租户环境中实现更好的隔离。
- 在标准基准测试和实际应用中进行了广泛的评估，证明了zsswap的性能提升，例如，与传统的块SSD交换相比，znswap的99百分位延迟降低了10倍，memcached的吞吐量提高了5倍，WAF降低了2.5倍。

## 2 背景 & 3 动机

**OS swap**

OS swap的初衷——当系统遇到内存压力时，它选择内存页，将其驱逐到交换设备(操作系统从页表中解映射选择要驱逐的页，并交换出该页，将其写入交换设备。)

swap-slots：Linux将交换设备上的空间划分为内存大小的块，称为交换槽。操作系统为每个被换出的页面分配一个新的插槽。

**Block SSD空间管理**

（FTL）维护的是LBA到物理地址的映射。例子：想要更新一个块，找一个新块直接写；改映射表；将原位置上的旧数据标为失效。这样的失效块需要垃圾回收，一方面需要空间上over-provisioning (OP)，另一方面设备端进行的GC会与用户I/O竞争带宽。

> WAF：外部的要写入的数据/ 在CG下的实际写入。OP越小，WAF越高。

**Zoned Namespace SSD(ZNS)**

新兴的“存储接口”，逻辑上的组织方式（每个区域大小在物理上与SSD的擦除块大小对齐），在一个Zone内必须顺序写（write、append，对于append，SSD在完成后才会返回具体写入的位置，这允许对一个Zone同时进行多个写请求）。Zone状态：Empty，Open，Full。要重写Zone，需要显示的清除，转换为Empty状态。

### 3 动机

"Flash的激增《复活》了swap的使用"

Swap不再仅仅是应对内存压力的手段，Swap在适度负载时可以充当内存扩展。（例如，优化文件支持和匿名内存页面之间的内存平衡。）但现有的工作更关注OS内的逻辑，本文将结合交换逻辑与SSD的行为对Linux Swap的性能进行深入分析。

#### 3.1  SSD Swap中的异常

- GC不能感知已释放的交换槽
- 交换缓存不能感知GC
- GC不了解页面访问模式
- GC不了解OS的性能隔离

再次观察图1，这种下降是意料之中的，因为GC开销与主动更新的数据量成比例增长。
然而，当设备几乎为空（仅占其容量的10%）时，不应出现下降。

<img src="ZNS.assets/image-20231114102732571.png" alt="image-20231114102732571" style="zoom:67%;" />

根本原因是设备侧GC没有意识到操作系统丢弃了一些交换出的页面，并没有使其对应的交换插槽无效，操作系统默认情况下不会通知SSD。因此，交换设备的实际占用率远高于操作系统可见的占用率，从而导致更高的GC开销。

为了解决上述问题，大多数SSD都支持了**TRIM**命令。

然而在实践中，流行的Linux发行版（例如Debian、Ubuntu）禁止使用TRIM命令进行交换。原因包括TRIM调度开销、TRIM命令的长延迟以及支持异步TRIM的复杂性。作者简单测试了当显式启用交换的TRIM时的情况（略），Linux优化后的TRIM命令与不启用TRIM效果一致

总之：TRIM开了不如不开。（swapon手册中也是这样注释的）

>在Linux系统中，交换槽（swap slot）是指用于存储交换空间（swap space）中的数据的固定大小的块。

#### 3.2 在ZNS上做Swap的可能

ZNS ssd提供了对物理数据放置的更好控制，从而支持应用程序逻辑和设备管理之间更紧密的耦合，并且已经被证明可以为生产Key-Value-Stores提供新的优化机会。这些结果激发了一种新的GC-swap子系统协同设计，它可以利用这种耦合来缓解上述传统ssd的性能问题。

。。。

## 4 Design

ZNS解决了3个关键的设计目标

**主机端垃圾回收**

在ZNS中回收空间需要一个主机端进程：把碎片化的有效内容合并成一个新区，擦除被释放的旧区域。

主要挑战是最小化开销，因为与设备端GC不同，主机端GC直接与常规应用程序争用主机资源。

从本质上讲，我们需要以最小的成本将GC从设备上加载到CPU上，从而使其与Swap的集成更加紧密。



因为有上述限制，直接移植已有的GC实现不可行，（例如FTL中GC的实现需要维护千分之一大小的映射表）

但是ZNGC不需要维护额外的间接层：

znGC通过将内核的反向映射元数据与交换出的页面一起存储在SSD中，避免了额外的间接层。这意味着在进行垃圾回收时，不需要查找额外的数据结构或表来获取页面的映射信息。相反，这些映射信息直接附加在交换出的页面本身上。

**ZNGC-OS集成**

相对于设备端垃圾回收，集成后通过OS暴露的信息可以优化Swap的性能

例如：ZNGC可以识别操作系统无效的交换槽（swap slot），并避免不必要的复制，而无需使用其他方式。

**数据放置策略**

策略取决于执行环境，提供了几种策略

### 4.1 总览

![image-20231115015514214](ZNS.assets/image-20231115015514214.png)



### 4.2 znGC

znGC集成在kernel virtual memory (VM)中。作为守护进程，当空zone数较低时触发。（或通过zswap策略的明确请求）

相对于块ssd，被ZNGC移动的页面讲被分配一个新的主机可见地址。如果没有额外的转换层，ZNGC必须更新保存原始页面交换槽的页表，以反映新的位置。

为此，ZNGC将相关的反向映射元数据与数据一起存储在ZNS SSD的per-LBA中，以帮助以后更新页表。



哪些信息需要存储在页面元数据中以保证反向映射在其生命周期内保持正确?

——Linux中已实现的反向映射方案

![image-20231115024036963](ZNS.assets/image-20231115024036963.png)





### 4.3 ZNGC-swap一体化

a）物理zone（空间）信息：每个空间与swap-slots的映射相关联，映射存储了每个swap-slot的状态。这样ZNGC和OS就可以立马知道swap-slot的状态转变，不需要TRIM和截断阈值来管理交换缓存。

b）交换空间抽象：可以被用来swap-slot分配的活跃空间通过交换空间抽象进行暴露，从而避免管理物理空间的复杂性。

c）ZNSwap策略：提供一系列接口使得可以定制化空间分配策略和回收策略。

d）接口：本文定义了三个标准api，单核策略、冷热策略和进程策略，分别是对每个核的数据、冷热数据和进程数据进行性能隔离。



## 评估

Ubuntu 20.04  Linux Kernel 5.12 

512G DDR4 

1T 西数ZN540 + 1T SSD

交换空间大小 = 系统内存大小 ，其他剩余的空间填充数据。

**Facebook memcached-ETC**
其中 90% 的请求在 10% 的key上。

![image-20231122174711316](ZNS.assets/image-20231122174711316.png)

## 评估

![image-20231115032938106](ZNS.assets/image-20231115032938106.png)



### 反向映射

匿名页反向映射是Linux内核中的一种机制，用于解除物理页与进程虚拟地址空间之间的映射关系。这个机制主要分为匿名页映射和文件页映射两种类型。下面将详细介绍匿名页反向映射的过程和anon_vma结构的作用。

1. 匿名页反向映射过程：
   - 当内核需要回收一个物理页时，需要先解除该物理页与进程虚拟地址空间的映射关系。
   - 反向映射机制通过查找物理页的映射关系，找到所有映射到该物理页的进程虚拟地址空间。
   - 反向映射过程主要涉及三个关键的数据结构：struct vm_area_struct (VMA)、struct anon_vma (AV)和struct anon_vma_chain (AVC)。
   - VMA用于描述进程的虚拟地址空间，其中的anon_vma_chain成员用于链接VMA和AV。
   - AV用于管理匿名页面映射的所有VMA，物理页的struct page中的mapping成员指向该结构体。
   - AVC是一个链接VMA和AV的桥梁，每个AVC都有一组对应的VMA和AV。AV会将与其关联的所有AVC存储在一个红黑树中。
2. anon_vma结构的作用：
   - anon_vma结构用于管理匿名页面对应的所有VMA。
   - 它可以通过物理页的mapping成员找到与之关联的AV。
   - AV中的rb_root红黑树存储了与该AV关联的所有AVC，通过遍历红黑树可以找到所有映射到该物理页的VMA。

通过匿名页反向映射机制，内核可以有效地解除物理页与进程虚拟地址空间之间的映射关系，并且可以快速找到所有映射到该物理页的VMA。这对于内核的内存管理非常重要。

>### Linux Swap
>
>1. 交换页面：当需要将数据页写入Swap空间时，Linux会将这些页面标记为“交换出”。数据页的内容将被写入Swap分区或Swap文件中，以释放内存供其他进程使用。
>2. 程序恢复：如果系统需要访问已经被交换出的页面，Linux会将这些页面重新读取到内存中。这将导致其他数据页被交换出，以便为需要的页面腾出空间。
>3. Swap空间的管理：Linux会定期检查Swap空间的使用情况，并根据需要进行Swap页面的调度和重新分配。这包括根据页面的活跃性和访问模式来决定哪些页面应该被换入或换出。
>
>### Swap Cache
>
>- Swap Cache是指交换分区中的缓存区域，类似于文件系统中的page cache。
>- Swap Cache用于存储匿名页（即没有文件背景的页面）的内容，这些页面在即将被swap-out时会被放进swap cache，但通常只存在很短暂的时间，因为swap-out的目的是为了腾出空闲内存。
>- 曾经被swap-out现在又被swap-in的匿名页也会存在于swap cache中，直到页面中的内容发生变化或者原来使用过的交换区空间被回收。
>
>Swap Cache（交换缓存）是Linux操作系统中的一种缓存机制，用于提高对Swap分区的读取性能。它是在内核中实现的一种缓存层，用于存储最近从Swap分区中读取的数据页，以便在需要时可以更快地访问这些页面。
>
>当Linux系统需要将数据页从Swap分区中读取回内存时，数据页会首先被放置到Swap Cache中。这样，如果后续的访问请求需要读取相同的数据页，内核可以直接从Swap Cache中获取数据，而无需再次访问慢速的Swap分区。



# ZNS

ZNS: Avoiding the Block Interface Tax for Flash-based SSDs

https://www.usenix.org/system/files/atc21-bjorling.pdf

目前的基于闪存的SSD仍然使用几十年前的块接口，存在问题：容量过配置、用于页映射表的DRAM空间开销、垃圾收集开销以及主机软件复杂性（为了减少垃圾回收）方面的大量开销。

通过暴露闪存擦除块边界和写入顺序规则，ZNS接口要求主机软件解决这些问题。展示了启用对ZNS SSD的支持所需的工作，并展示了修改后的f2fs和RocksDB版本如何利用ZNS SSD以实现与具有相同物理硬件的块接口SSD相比更高的吞吐量和更低的尾延迟。

## 1 Intro

最初引入块接口是为了隐藏硬盘媒体的特性并简化主机软件，块接口在多个存储设备的世代中表现良好，对于基于闪存的SSD，支持块接口的性能和运营成本正在急剧增加。

下图描述了GC给吞吐速度带来的影响，也可以看到更大的OP配置为GC带来了性能提升。但都不如ZNS。

![image-20240106163424244](ZNS.assets/image-20240106163424244.png)

本文描述了ZNS接口以及它是如何避免块接口带来的开销的（第2节）。我们描述了ZNS设备所放弃的责任，使它们能够减少性能不可预测性并通过减少对设备内资源的需求来显著降低成本（第3.1节）。此外，我们还描述了ZNS的一个预期后果：主机需要以擦除块的粒度来管理数据。将FTL（Flash Translation Layer）的责任转移到主机上并不如与存储软件的数据映射和放置逻辑集成来得有效，这是我们提倡的方法（第3.2节）。 

这篇论文提出了五个关键贡献：

1. 首次对生产中的ZNS SSD进行了研究论文中的评估，并直接将其与使用相同硬件平台和可选的多流支持的块接口SSD进行了比较。
2. 对新兴的ZNS标准及其与先前SSD接口的关系进行了回顾。
3. 描述了将主机软件层适应ZNS SSD的经验教训。
4. 描述了一系列跨足整个存储堆栈的变化，以实现ZNS支持，包括对Linux内核、f2fs文件系统、Linux NVMe驱动和分区块设备子系统、fio基准测试工具的更改，以及相关工具的开发。
5. 引入了ZenFS，作为RocksDB的存储后端，以展示ZNS设备的完整性能。所有代码更改都已开源并合并到了各自的官方代码库中。、

论文的第2部分讨论了"Zoned Storage Model"，描述了存储设备的发展历史以及传统的块接口模型，以及ZNS模型的背景和特性。这部分包括了以下内容：

- 描述了多年来存储设备一直以一维数组的形式暴露其主机容量，以及如何通过块接口来进行数据读取、写入或覆写。
- 讨论了块接口的设计初衷，即紧密跟踪当时最流行的设备特性，即硬盘驱动器（HDDs）。
- 介绍了随着时间的推移，块接口提供的语义成为了应用程序所依赖的默契协定。
- 引入了Zoned Storage模型的概念，最初是为了Shingled Magnetic Recording（SMR）HDDs而引入的，旨在创造与块接口兼容成本无关的存储设备。

论文进一步详细讨论了ZNS模型的基本特征以及与块接口的比较。

## 2 Zone 存储模型

### 2.1 块接口的开销

FTL异地更新带来性能不可预测性

Over-provision（最多28%）

映射表DRAM

### 2.2 现有工作

具有流支持的SSD（Stream SSDs）和开放通道SSD（Open-Channel SSDs）。

Stream SSDs允许主机使用流提示标记其写入命令。流提示标记由Stream SSD解释，允许它将传入的数据区分到不同的擦除块中，从而提高了整体SSD性能和媒体寿命。然而，Stream SSDs要求主机要仔细标记具有相似寿命的数据，以减少垃圾回收。如果主机将不同寿命的数据混合到同一流中，Stream SSDs的行为类似于块接口SSD。此外，Stream SSD必须携带资源来管理这种事件，因此它们无法摆脱块接口SSD的额外媒体超额配置和DRAM成本。论文中还在第5.3节中对Stream SSD和ZNS SSD的性能进行了比较。

开放通道SSD允许主机和SSD通过一组连续的LBA块来协同工作。OCSSDs可以将这些块暴露出来，以便它们与媒体的物理擦除块边界对齐。这消除了设备内垃圾回收的开销，并减少了媒体超额配置和DRAM的成本。在OCSSDs中，主机负责数据的放置，包括底层媒体可靠性管理，如均衡磨损，并根据OCSSD类型处理特定的媒体故障特性。这有潜力改善SSD性能和媒体寿命，但主机必须管理不同SSD实现之间的差异以确保耐用性，使界面难以采用，并需要持续的软件维护。

### 2.3 Zone


"zone"（分区）：每个zone表示SSD的逻辑地址空间中的一个区域，可以任意读取，但必须按顺序写入，覆写必须显式地进行重置。写入约束由每个zone的状态机和写入指针来执行。

*state：*每个区域都有一个状态，确定给定区域是否可写，具有以下状态：EMPTY、OPEN、CLOSED或FULL。区域从EMPTY状态开始，在写入时转换为OPEN状态，最终在完全写满时转换为FULL状态。设备可能会进一步限制同时处于OPEN状态的区域数量，例如，由于设备资源或媒体限制。如果达到限制并且主机尝试写入新区域，那么必须将另一个区域从OPEN状态转换为CLOSED状态，以释放设备上的资源，如写入缓冲区。CLOSED区域仍然可写，但必须在提供额外写入之前再次转换为OPEN状态。

*write pointer：*每个区域的写指针指定可写区域内的下一个可写LBA，仅在EMPTY和OPEN状态下有效，在每次写入时刷新。

## 3 Evolving towards ZNS

### 3.1 硬件

ZNS为终端用户带来了很多好处，但它在固态硬盘 FTL 的设计中引入了以下折衷方案（trade-off）

**区域大小（Zone Sizing）**

SSD的写入能力与擦除块的大小直接相关。在块接口SSD中，擦除块的大小选择使数据跨越多个闪存芯片以提高读写性能，并通过每个条带的奇偶校验来防护芯片级别及其他媒体故障。SSD通常有一个条带，包括16-128个芯片的闪存块，这相当于拥有几百兆字节到几个千兆字节写入能力的区域。大区域减少了主机数据放置的自由度，因此提倡尽可能小的区域大小，同时仍提供芯片级保护和适当的区域读写性能。

**映射表（Mapping Table）**

在块接口SSD中，使用板载的DRAM维护全关联映射表。这种精细的映射提高了垃圾收集性能。但ZNS使用更粗的粒度的映射，以可擦除块级别 or 混合方式维护映射表。

### 3.2 主机端适配

顺序写型应用是采用ZNS的首选，例如LSM-tree数据库。就地更新型应用就很难搞。下面介绍主机软件适应ZNS的三种方法。

1. **主机端闪存转换层（HFTL）**：HFTL充当ZNS SSD的写入语义与执行随机写入及就地更新的应用之间的中介。它的职责与SSD中的FTL相似，但仅限于管理转换映射和相关的垃圾回收。尽管HFTL的职责较SSD FTL小，但它必须管理其对CPU和DRAM资源的使用，因为这些资源与主机应用共享。HFTL简化了与主机端信息的整合，增强了数据放置和垃圾回收的控制，并向应用程序提供传统块接口。目前，例如dm-zoned、dm-zap、pblk和SPDK的FTL等工作显示了HFTL的可行性和应用性，但目前只有dm-zap支持ZNS SSD。
2. **文件系统**：更高级别的存储接口（例如POSIX文件系统接口）允许多个应用通过共同的文件语义访问存储。通过将区域与存储堆栈的更高层次整合，即确保主要是顺序工作负载，可以消除与HFTL和FTL数据放置及相关间接开销。这也允许使用高级存储堆栈层已知的额外数据特性来改善设备上的数据放置。但是，目前大多数文件系统主要执行就地写入，适应区域存储模型通常很困难。然而，一些文件系统（如f2fs、btrfs和zfs）表现出过度顺序的特性，可能更适合ZNS。
3. **针对顺序写入操作的应用**：对于主要进行顺序写入的应用来说，ZNS是一个很好的选择。例如，基于日志结构合并（LSM）树的数据库。这些应用因为其顺序写入的特性，与ZNS接口的设计高度兼容。反之，就地更新为主的应用则更难支持，除非对核心数据结构进行根本性修改。



## 4 实现


- Linux支持	Zoned Block Device (ZBD)
- f2fs
- fio测试增加了ZNS属性
- ZenFS

- Linux支持  (对内核对用户的接口，如util-linux等)	
- 修改f2fs以支持ZNS
- fio测试增加了ZNS
- 开发了ZenFS作为RocksDB的后端

![image-20240311192804707](ZNS.assets/image-20240311192804707.png)


### 4.1 Linux支持

**Zoned Block Device（ZBD）子系统**：这是一个抽象层，为不同类型的区域存储设备提供统一的区域存储API。它既提供内核API，也提供基于ioctl的用户空间API，支持设备枚举、区域报告和区域管理（例如，区域重置）。应用程序如fio利用用户空间API发出与底层区域块设备的写特性一致的I/O请求。

**为Linux内核添加ZNS支持**：修改了NVMe设备驱动程序，以便在ZBD子系统中枚举和注册ZNS SSD。为了支持评估中的ZNS SSD，ZBD子系统API被进一步扩展，以暴露每个区域的容量属性和活动区域的限制。

**区域容量（Zone Capacity）**：内核维护着区域的内存表示（一组区域描述符数据结构），这些由主机单独管理，除非出现错误，否则应该从特定磁盘刷新区域描述符。区域描述符数据结构增加了新的区域容量属性和版本控制，允许主机应用检测这个新属性的可用性。fio和f2fs都更新了以识别新的数据结构。fio只需避免超出区域容量发出写I/O，而f2fs则需要更多的改变。



f2fs以段为单位管理容量，通常是2MiB的块。对于分区块设备，f2fs将多个段管理为一个部分，其大小与分区大小对齐。f2fs按照部分段的段按顺序写入，不支持部分可写区域。为了在f2fs中添加对分区容量属性的支持，内核实现和相关的f2fs工具增加了两种额外的段类型，除了三种传统的段类型（即自由、打开和满）之外：一个无法使用的段类型，用于映射分区中不可写入的部分，以及一个部分段类型，用于处理段的LBA跨越分区的可写和不可写的LBA的情况。部分段类型明确允许在段块大小和特定分区的分区容量不对齐的情况下进行优化，利用分区的所有可写容量。


**限制活动区域（Limiting Active Zones）**：由于基于闪存的SSD的性质，同时处于打开或关闭状态的区域数量有严格的限制。在区域块设备枚举时检测到这个限制，并通过内核和用户空间API暴露。SMR HDD没有这样的限制，因此这个属性初始化为零（即无限）。f2fs将这个限制与可以同时打开的段数相关联。

**对f2fs的修改**：f2fs要求其元数据存储在传统块设备上，需要单独的设备。在修改中没有直接解决这个问题，因为评估中的ZNS SSD将其一部分容量作为传统块设备暴露。如果ZNS SSD不支持，可以添加类似于btrfs的就地写入功能，或者小的转换层可以通过传统块接口在ZNS SSD上暴露一组限制区域。



**性能考量**：所有区域存储设备都禁用了Slack Space Recycling（SSR）功能（即随机写入），这降低了整体性能。然而，由于ZNS SSD实现了更高的整体性能，即使在启用SSR的块接口SSD上，也展示了更优越的性能。



### 4.2 RocksDB Zone Support

> ZenFS

*（LSM-tree的介绍）*

LSM树的多层级结构：LSM树包含多个层级，其中第一层（L0）在内存中管理，并定期或在满时刷新到下一层。刷新之间的中间更新通过写前日志（WAL）持久化。其余层级（L1; ...; Ln）维护在磁盘上。新的或更新的键值对最初被追加到L0，在刷新时，键值对按键排序，然后以排序字符串表（SST）文件的形式写入磁盘。

层级大小和SST文件：每个层级的大小通常是上一层的倍数，每个层级包含多个SST文件，每个SST文件包含一个有序的、不重叠的键值对集合。通过显式的压缩过程，一个SST的键值对从一个层级（Li）合并到下一个层级（Li+1）。压缩过程从一个或多个SST中读取键值对，并将它们与下一层的一个或多个SST中的键值对合并。合并的结果存储在一个新的SST文件中，并替换LSM树中的合并SST文件。因此，SST文件是不可变的，顺序写入的，并作为单个单元创建/删除。

RocksDB的存储后端支持：RocksDB通过其文件系统包装器API支持不同的存储后端，这是一个统一的抽象，用于RocksDB访问其磁盘上的数据。核心API通过唯一标识符（例如，文件名）识别数据单元，如SST文件或写前日志（WAL），并映射到字节寻址的线性地址空间（例如，文件）。每个标识符支持一组操作（例如，添加、移除、当前大小、利用率），除了随机访问和顺序只读和写入字节寻址语义。这些与文件系统语义密切相关，在文件系统中，通过文件访问标识符和数据，这是RocksDB的主要存储后端。通过使用文件系统管理文件和目录，RocksDB避免了管理文件区域、缓冲和空间管理，但也失去了将数据直接放置到区域中的能力，这阻止了端到端的数据放置到区域中，从而降低了总体性能。

#### 4.2.1 ZenFS 结构

ZenFS是一个针对ZNS SSD设计的存储后端，它实现了一个最小的磁盘文件系统，与RocksDB的文件包装API进行集成。ZenFS通过小心地将数据放置到不同的区域（zones）中，同时遵守它们的访问约束，与设备端的区域元数据进行协作（例如，写指针），降低了与持久性相关的复杂性。ZenFS的主要结构包括：

*（LSM-tree的介绍，略）*

### ZenFS存储后端

ZenFS是为RocksDB设计的，专门用于在分区存储设备（例如ZNS SSD）上高效存储数据的文件系统。它充分利用了RocksDB的LSM树结构及其不可变的、仅顺序压实过程，为分区存储设备提供了一种优化的数据管理方法

RocksDB 通过其文件系统包装器 API 提供对独立存储后端的支持，该 API 是 RocksDB 访问其磁盘数据的统一抽象。从本质上讲，包装器 API 通过唯一标识符（例如文件名）识别数据单元，例如 SST 文件或预写日志 (WAL)，该标识符映射到一个可按字节寻址的线性地址空间（例如文件）。每个标识符除了随机访问和仅顺序的可按字节寻址的读写语义之外，还支持一组操作（例如，添加、删除、当前大小、利用率）。这些操作与文件系统语义密切相关，其中标识符和数据可通过文件访问，这是 RocksDB 的主要存储后端。通过使用管理文件和目录的文件系统，RocksDB 避免了管理文件范围、缓冲和空闲空间管理，但也失去了将数据直接放置到区域中的能力，这阻止了端到端数据放置到区域中，因此降低了整体性能。

>RocksDB 本身有一个文件系统包装器，称为 `Env`。`Env` 是一个抽象接口，为 RocksDB 提供了对底层文件系统的访问。默认 `Env` 实现是 `PosixEnv`，也有WindowsEnv,MemoryEnv,S3Env
>
>通过使用 `Env` 接口，RocksDB 可以与不同的文件系统交互，而无需修改其核心代码。因此，**RocksDB 的底层通常是普通的文件系统**，例如 ext4、NTFS 或 XFS。但是，通过使用 `Env` 接口，RocksDB 也可以与其他类型的存储系统交互，例如云存储或分布式文件系统。



#### 4.2.1 ZenFS 结构

ZenFS 存储后端实现了一个最小的磁盘文件系统，并使用 RocksDB 的文件包装器 API 将其集成。它在满足访问限制的同时小心地将数据放置到区域中，并在写入时与设备端的区域元数据（例如，写入指针）协作，从而降低了与持久性相关的复杂性。ZenFS 的主要组件如图 4 所示，并如下所述。


![image-20240108170518019](ZNS.assets/image-20240108170518019.png)

**Journaling and Data:** ZenFS定义了两种类型的区域：日志（journal）区域和数据（data）区域。日志区域用于恢复文件系统的状态，维护超级块数据结构以及将WAL（Write-Ahead Logging）和数据文件映射到区域。而数据区域则存储文件内容。

**Extents:** RocksDB的数据文件被映射并写入一组extent（数据块）。一个extent是一个可变大小、块对齐的连续区域，按顺序写入到数据区域中，包含与特定标识符相关的数据。

每个Zone可以存储多个extents，但extents不会跨越Zone。分配和释放extent的事件将记录在内存数据结构中。当文件关闭或通过RocksDB的fsync调用要求将数据持久化时，写入日志。内存数据结构跟踪extents到区域的映射，一旦在区域中分配extents的所有文件都被删除，该区域就可以被重置和重用。

每个Zone可以存储多个extents，但extents不会跨越Zone。分配和释放extent的事件将记录在内存数据结构中。当文件关闭或通过RocksDB的fsync调用要求将数据持久化时，写入日志。内存数据结构跟踪extent到zone的映射，一旦分配了extent的所有文件在区域中被删除，该区域就可以被重置并重新使用。

**Superblock：**超级块（Superblock）是初始化和从磁盘上恢复ZenFS状态的初始入口点。超级块包含当前实例的唯一标识符（UUID）、魔术值和用户选项。在超级块中的唯一标识符允许用户在系统上块设备枚举的顺序发生变化时仍然能够识别文件系统。

**Journal：**日志（Journal）的责任是维护超级块和WAL（Write-Ahead Logging）以及数据文件到区域的映射关系，这些映射关系是通过extents进行的。

日志状态存储在专用的日志区域上，并位于设备的前两个非离线区域上。在任何时刻，其中一个区域被选为活动日志区域，并将更新持久化到日志状态。一个日志区域有一个头部，存储在特定区域的开头。头部包含一个序列号（每当初始化新的日志区域时递增）、超级块数据结构以及当前日志状态的快照。在头部存储后，该区域的剩余可写容量用于记录日志的更新。

日志状态存储在专用的日志区域上，并位于设备的前两个非离线区域上。在任何时刻，其中一个区域被选为活动日志区域(另一个是它的备份)，并将更新持久化到日志状态。一个日志区域有一个头部，存储在特定区域的开头。头部包含一个序列号（每当初始化新的日志区域时递增）、超级块数据结构以及当前日志状态的快照。在头部存储后，该区域的剩余可写容量用于记录日志的更新。



如何恢复日志状态？分三步：

1. **读取两个日志区域的第一个LBA（逻辑块地址）**：为了确定每个区域的序列号，必须读取两个日志区域的第一个LBA。其中序列号较高的日志区域被视为当前活动区域。
2. **读取活动区域的完整头部并初始化初始超级块和日志状态**：这一步涉及读取活动日志区域的完整头部信息，并据此初始化文件系统的初始超级块和日志状态。
3. **应用日志更新到头部的日志快照**：更新的数量由区域的状态和其写入指针决定。如果区域处于打开（或关闭）状态，只有直到当前写入指针值的记录被重放到日志中。而如果区域处于满状态，头部之后存储的所有记录都被重放。

如果区域已满，在恢复后，会选择并初始化一个新的活动日志区域，以便持续日志更新的持久化。初始日志状态是由类似于现有文件系统工具的外部实用程序创建并持久化的。它将初始序列号、超级块数据结构和一个空的日志快照写入第一个日志区域。当RocksDB初始化ZenFS时，将执行上述恢复过程。

此外，还提到了RocksDB在不同SST（排序字符串表）文件大小下的写放大、运行时间和尾延迟表现。这显示了不同配置对RocksDB性能的影响，特别是在没有速率限制的读写（RW）和写入速率限制为20MiB/s的读写（RWL）期间。


**数据区域中的可写容量**：理想的分配，以实现最大容量使用率，只有在文件大小是区域可写容量的倍数时才能实现，这样才能在完全填满所有可用容量的同时将文件数据完全分隔到区域中。RocksDB允许配置文件大小，但这只是一个建议，由于压缩和压缩过程的结果，大小会有所变化，因此无法保证精确大小。ZenFS通过允许用户配置数据区域完成的限制来解决这个问题，指定区域剩余容量的百分比。这使得用户可以指定文件大小建议，例如，设备区域容量的95%，通过设置完成限制为5%。这样文件大小就可以在一个限制范围内变化，仍然能够通过区域实现文件分隔。

**数据区域选择**：ZenFS采用最佳尝试算法来选择最佳区域存储RocksDB数据文件。RocksDB通过在写入文件之前为文件设置写入生命周期提示来分隔WAL和SST级别。在首次写入文件时，为存储分配一个数据区域。ZenFS首先尝试根据文件的生命周期和区域中存储数据的最大生命周期找到一个区域。如果找到多个匹配项，则使用最接近的匹配项。如果没有找到匹配项，则分配一个空区域。

**活动区域限制**：ZenFS必须遵守由分区块设备指定的活动区域限制。运行ZenFS需要至少三个活动区域，分别分配给日志、WAL和压缩过程。为了提高性能，用户可以控制并发压缩的数量。实验表明，通过限制并发压缩的数量，RocksDB可以在写性能受限的情况下使用少至6个活动区域，而超过12个活动区域并不会带来任何显著的性能优势。

**直接I/O和缓冲写入**：ZenFS利用了SST文件的写入是顺序的和不可变的这一事实，对SST文件进行直接I/O写入，绕过内核页面缓存。对于其他文件，例如WAL，ZenFS在内存中缓冲写入，并在缓冲区满、文件关闭或RocksDB请求刷新时刷新缓冲区。如果请求刷新，缓冲区将被填充到下一个块边界，并将有效字节数的范围存储在日志中。这种填充会导致一定量的写放大，但这不是ZenFS特有的，在传统文件系统中也会这样做。

## 5 评估


**数据区域中的可写容量**

理想的分配（随着时间的推移实现最大容量使用率）只能在文件大小是区域可写容量的倍数的情况下实现，允许文件数据在区域中完全分离，同时填满所有可用容量。文件大小可以在 RocksDB 中配置，但该选项只是一个建议，并且大小会根据压缩和整理过程的结果而有所不同，因此无法实现确切的大小。

ZenFS 通过允许用户配置数据区域完成的限制来解决这个问题，指定剩余区域容量的百分比。这允许用户通过将完成限制设置为 5% 来指定文件大小建议，例如设备区域容量的 95%。这允许文件大小在限制范围内变化，并且仍然按区域实现文件分离。如果文件大小变化超出指定限制，ZenFS 将通过使用其区域分配算法（如下所述）确保利用所有可用容量。区域容量通常大于 RocksDB 推荐的文件大小 128 MiB，为了确保增加文件大小不会增加 RocksDB 写放大和读取尾部延迟，我们测量了对不同文件大小的影响。表 2 表明增加 SST 文件大小不会显着降低性能。

**数据区域选择**

ZenFS 采用尽力而为的算法来选择存储 RocksDB 数据文件的最佳区域。RocksDB 通过在写入文件之前为文件设置写生命周期提示来分隔 WAL 和 SST 级别。在第一次写入文件时，将分配一个数据区域进行存储。ZenFS 首先尝试根据文件的生命周期和存储在该区域中的数据的最大生命周期来查找区域。只有当文件生命周期小于存储在该区域中的最旧数据时，匹配才有效，以避免延长该区域中数据的生命周期。如果找到多个匹配项，则使用最接近的匹配项。如果没有找到匹配项，则分配一个空区域。如果文件填满了已分配区域的剩余容量，则使用相同的算法分配另一个区域。请注意，写生命周期提示提供给任何 RocksDB 存储后端，因此也传递给其他兼容文件系统，并且可以与支持流的 SSD 一起使用。我们在 §5.3 中比较了传递提示的这两种方法。通过使用 ZenFS 区域选择算法和用户定义的可写容量限制，未使用的区域空间或空间放大保持在 10% 左右。

**活动区域限制**

ZenFS 必须遵守分区块设备指定的活动区域限制。要运行 ZenFS，需要至少三个活动区域，这些区域分别分配给日志、WAL 和整理进程。为了提高性能，用户可以控制并发整理的数量。我们的实验表明，通过限制并发整理的数量，RocksDB 可以在仅有 6 个活动区域的情况下工作，同时限制写性能，而超过 12 个活动区域不会增加任何显着的性能优势。

**直接 I/O 和缓冲写入**

ZenFS 利用了对 SST 文件的写入是顺序且不可变的事实，并对 SST 文件执行直接 I/O 写入，绕过内核页面缓存。对于其他文件，例如 WAL，ZenFS 会将写入缓冲到内存中，并在缓冲区已满、文件已关闭或 RocksDB 请求刷新时刷新缓冲区。如果请求刷新，则将缓冲区填充到下一个块边界，并将包含有效字节数的范围存储在日志中。填充会导致少量的写放大，但这并不是 ZenFS 独有的，并且在传统文件系统中也会以类似的方式完成。

## 5 实验评估



- Dell R7515 系统
- 16 核 AMD Epyc 7302P CPU
- 128GB DRAM (8 x 16GB DDR4-3200Mhz)
- Ubuntu 20.04 （更新到 5.9 Linux 内核）
- 在 RocksDB 6.12 上进行，其中 ZenFS 包含为后端存储插件。
- 有一块**“生产 SSD 硬件平台“**，可以暴露为块接口 SSD 或 ZNS SSD：

![image-20240311200430552](ZNS.assets/image-20240311200430552.png)

>他有一块平台，可以切换 块接口 or Zone接口。“apples-to-apples comparison”是一个英语短语，意为在相同的基础上进行比较，以确保比较的公平性和准确性。

**5.1 原生设备 I/O 性能**

我们将块接口 SSD 地址空间划分为 LBA 范围，这些范围具有与 ZNS SSD 暴露的区域容量相同数量的 LBA。这些区域或 LBA 范围遵循与 ZNS 相同的顺序写入约束，但是通过在写入之前修剪 LBA 范围来模拟区域重置。我们在 SSD 使用给定工作负载达到稳态后测量性能。

持续写入吞吐量：我们评估 SSD 吞吐量以显示内部 SSD 垃圾回收对吞吐量的影响及其消耗主机写入的能力。
**5.2 端到端应用程序性能**

- RocksDB 在 ZNS SSD 上运行时，读写吞吐量提高了 2 倍，随机读尾部延迟降低了一个数量级。

**5.3 与 SSD 流的端到端性能比较**

- 与支持流的块接口 SSD 相比，ZNS SSD 的吞吐量提高了 44%，尾部延迟降低了一半







# 模拟器

### QEMU 

西交实验：https://github.com/MiracleHYH/CS_Exp_ZNS

https://miracle24.site/other/cs-exp-zns-1/

### FEMU(tong)

 https://www.usenix.org/system/files/conference/fast18/fast18-li.pdf

FEMU配置与源码浅析https://blog.xiocs.com/archives/46/

与原生的 Qemu-nvme 相比，Femu 的扩展主要集中在延迟仿真上。

### ConfZNS

https://github.com/DKU-StarLab/ConfZNS ，CCF C

### NVMeVirt

NVMeVirt: A Versatile Software-defined Virtual NVMe Device，FAST 23

ZenFS + RocksDB + nvmevirt 配置ZNS模拟环境:

https://www.notion.so/znsssd/NVMEvirt-NVMEvirt-RockDB-Zenfs-7292a6396ed84fc29010a8d0ed768d9b?pvs=25



上交毕设：实现*ZNS* *SSD*模拟器，然后基于模拟器设计适配的LSM Tree https://github.com/adiamoe/LSM-based-on-ZNS-SSD



# 其他相关项目

### [Dantali0n/OpenCSD](https://github.com/Dantali0n/OpenCSD)

OpenCSD: eBPF Computational Storage Device (CSD) for Zoned Namespace (*ZNS*) *SSDs* in QEMU

### SZD

[SimpleZNSDevice](https://github.com/Krien/SimpleZNSDevice)

基于SPDK做的的ZNS的封装，可以让用户不费吹灰之力就能开发 ZNS 设备。

### **[bpf-f2fs-zonetrace](https://github.com/pingxiang-chen/bpf-f2fs-zonetrace)**

基于eBPF的Zone可视化工具

ZoneTrace是一个基于eBPF的程序，可以在ZNS SSD上的F2FS上实时可视化每个区域的空间管理，而无需任何内核修改。我们相信ZoneTrace可以帮助用户轻松分析F2FS，并开辟几个关于ZNS SSD的有趣研究课题。

### F2FS

(Flash-Friendly File System，三星)

原文，https://www.usenix.org/system/files/conference/fast15/fast15-paper-lee.pdf

非官方仓库，https://github.com/unleashed/f2fs-backports

### ZenFS

ZNS文件系统，for RocksDB，西数。 https://github.com/westerndigitalcorporation/zenfs

### zonefs-tools

一个极简的ZNS文件系统，西数。https://github.com/westerndigitalcorporation/zonefs-tools

### OS接口文档

https://zonedstorage.io/docs/introduction

# 设备

znskv中使用的盘

![image-20231208114504674](./ZNS.assets/image-20231208114504674.png)

### 硬件接口

![img](ZNS.assets/v2-1057134427f228d44445ae84730da650_1440w.webp)





U.2 (SFF-8639)https://zhuanlan.zhihu.com/p/568688937?utm_id=0

![img](ZNS.assets/v2-6a9818b238f03d0864210ab4fc8ddc6b_1440w.webp)

### 设备安装记录

https://www.notion.so/znsssd/Disk-2b750be455a2459bb346556567b2553a









# 



































# 其他问题

>现在没有了逻辑块地址-虚拟块地址的转换，数据在盘中的真实地址暴露给应用，是否可以（更好地利用空间局部性）使得prefetch的效果更好？

常见的磁盘预取器和开源存储引擎中使用的磁盘预取算法

磁盘预取是一种优化技术，通过提前将数据从磁盘读取到内存中，以减少磁盘I/O操作的等待时间。常见的磁盘预取器和开源存储引擎中使用的磁盘预取算法如下：

1. Linux Page Cache预读：Linux操作系统中的Page Cache是一种内存缓存机制，它可以将磁盘上的数据预先加载到内存中，以提高读取性能。Linux Page Cache预读算法会根据文件的访问模式和访问模式的历史记录来预测下一次可能访问的数据，并提前将这些数据加载到内存中[[2\]](https://xiazemin.github.io/linux/2020/04/01/pagecache.html)。
2. MySQL InnoDB存储引擎的磁盘预取算法：MySQL InnoDB存储引擎使用了一种称为"DoubleWrite Buffer"的技术来提高磁盘写入性能。在写入数据到磁盘之前，InnoDB会将数据先写入到一个内存缓冲区中，然后再将数据从缓冲区写入到磁盘。这种方式可以减少磁盘的随机写入操作，提高写入性能[[2\]](https://xiazemin.github.io/linux/2020/04/01/pagecache.html)。
3. RocksDB存储引擎的磁盘预取算法：RocksDB是一个开源的键值存储引擎，它使用了一种称为"Block-based Table"的存储结构。在读取数据时，RocksDB会根据数据的访问模式和历史记录来预测下一次可能访问的数据块，并提前将这些数据块加载到内存中。这种方式可以减少磁盘的随机读取操作，提高读取性能[[2\]](https://xiazemin.github.io/linux/2020/04/01/pagecache.html)。





>两步编程（Two-step programming）是一种在NAND闪存芯片中使用的编程方法。

这种方法特别设计用于提高数据的写入准确性和闪存芯片的寿命。在传统的闪存编程中，数据以一次性方式写入存储单元，但在两步编程中，这个过程被分成两个阶段：

1. **第一步**：在第一步中，数据被部分地写入存储单元。这通常包括将存储单元设置到一个中间的阈值电平。
2. **第二步**：在第二步中，数据被进一步细化或“调整”到其最终值。这个过程涉及更精细地控制电荷的注入，以确保数据被准确地写入。

两步编程的好处包括：

- **提高精度**：通过这种分阶段方法，可以更精确地控制电荷的流动，减少写入错误。
- **延长寿命**：减少了对闪存单元的应力，从而延长了其使用寿命。

这种技术在多层单元（MLC）和三层单元（TLC）NAND闪存中尤其重要，因为这些类型的闪存在存储多比特信息时需要更高的精确度。不过，两步编程也可能导致写入过程比一步编程更慢，因为需要额外的时间来细化数据的存储。





# kangaroo：SSD as cache

## 0 Ab

合并日志结构化缓存和组相联缓存，旨在降低DRAM和闪存写入的开销。
    - 系统由两个主要部分组成：**KLog**（一个小型的日志结构化闪存缓存）和**KSet**（一个大型的组相联闪存缓存）。
        - **KLog**作为一个暂存区，使得对象写入到**KSet**更加高效。它只使用少量的闪存（约5%）并且只需要最小的DRAM来索引其全部容量。
        - **KSet**在闪存页面中存储对象，并使用布隆过滤器（Bloom filter）有效地跟踪集合成员身份。
        - Kangaroo引入了**门槛准入策略**，允许它在减少写入的同时逐出对象。它确保将对象移动到KSet的写放大明显低于组相联缓存。

3. **操作流程**:
   - **查找操作**：Kangaroo通过首先检查DRAM缓存，然后检查KLog的索引，最后检查KSet的布隆过滤器来执行查找。
   - **插入操作**：对象首先被插入到DRAM缓存。从DRAM缓存逐出的对象要么被丢弃，要么被添加到KLog的索引和闪存日志中。从KLog逐出的对象要么被丢弃，要么被插入到KSet中。

4. **创新和优化**:
   - Kangaroo引入了创新技术来最小化写放大，通过同时将多个对象从KLog移动到KSet。
   - 系统设计在允许的写速率、DRAM大小和闪存大小的范围内是帕累托最优的，表现出比以前的设计更好的性能和更低的成本。
   - 它还提供了进一步的优化，以减少DRAM开销和缺失率，提高了缓存过程的整体效率。

总而言之，Kangaroo有效地解决了在闪存上有效缓存数十亿个小型对象的关键问题，提出了一个强大的解决方案，最小化了DRAM和闪存写入的开销。这一创新对于大规模系统（如社交媒体和物联网服务）特别有益，其中高效的缓存对于性能和成本效益至关重要【https://www.cs.cmu.edu/~csd-phd-blog/2022/kangaroo/】【7†source】【8†source】【9†source】。

## 0 Ab

合并日志结构化缓存和组相联缓存来克服这些限制，旨在降低DRAM和闪存写入的开销。
    - 系统由两个主要部分组成：**KLog**（一个小型的日志结构化闪存缓存）和**KSet**（一个大型的组相联闪存缓存）。
        - **KLog**作为一个暂存区，使得对象写入到**KSet**更加高效。它只使用少量的闪存（约5%）并且只需要最小的DRAM来索引其全部容量。
        - **KSet**在闪存页面中存储对象，并使用布隆过滤器（Bloom filter）有效地跟踪集合成员身份。
        - Kangaroo引入了**门槛准入策略**，允许它在减少写入的同时逐出对象。它确保将对象移动到KSet的写放大明显低于组相联缓存。

3. **操作流程**:
   - **查找操作**：Kangaroo通过首先检查DRAM缓存，然后检查KLog的索引，最后检查KSet的布隆过滤器来执行查找。
   - **插入操作**：对象首先被插入到DRAM缓存。从DRAM缓存逐出的对象要么被丢弃，要么被添加到KLog的索引和闪存日志中。从KLog逐出的对象要么被丢弃，要么被插入到KSet中。

4. **创新和优化**:
   - Kangaroo引入了创新技术来最小化写放大，通过同时将多个对象从KLog移动到KSet。
   - 系统设计在允许的写速率、DRAM大小和闪存大小的范围内是帕累托最优的，表现出比以前的设计更好的性能和更低的成本。
   - 它还提供了进一步的优化，以减少DRAM开销和缺失率，提高了缓存过程的整体效率。

总而言之，Kangaroo有效地解决了在闪存上有效缓存数十亿个小型对象的关键问题，提出了一个强大的解决方案，最小化了DRAM和闪存写入的开销。这一创新对于大规模系统（如社交媒体和物联网服务）特别有益，其中高效的缓存对于性能和成本效益至关重要【https://www.cs.cmu.edu/~csd-phd-blog/2022/kangaroo/】。

![image-20240713094634569](ZNS.assets/image-20240713094634569.png)

# ZoneKV

ZoneKV: A Space-Efficient Key-Value Store for ZNS SSDs，DAC23

来自中国科学技术大学和字节跳动公司。

按照LSM-Tree中每层的等级作为生命周期，调整区域放置。



https://ieeexplore.ieee.org/stamp/stamp.jsp?tp=&arnumber=10247926

## 0 摘要

- 提出了ZoneKV，一种针对ZNS SSDs的空间高效键值存储系统。
- 观察到现有的RocksDB适配到ZNS SSDs会导致区域碎片化和空间放大问题。
- 因此，我们提出了一个基于生命周期的区域存储模型和特定级别的区域分配算法，将生命周期相似的SSTables存储在同一区域。
- 在真实的ZNS SSD上评估了ZoneKV，结果显示ZoneKV能够减少高达60%的空间放大，并保持比RocksDB with ZenFS更高的吞吐量。

## 1 引言

- ZNS SSDs：是一种新型SSD，采用新的NVMe存储接口。它们将逻辑块地址（LBA）划分为多个相同大小的区域，每个区域只能顺序写入并在重置后再次使用。这种强制性的顺序写入允许ZNS SSDs进行更粗粒度的地址转换。此外ZNS SSDs将垃圾回收和数据放置的功能留给主机侧，这使得用户可以设计出有效技术来利用ZNS SSDs的优势，例如新的索引和缓冲区管理器。

- ZNS SSDs与LSM-tree（Log-Structured Merge-tree）的契合性： LSM-tree将随机写入转换为顺序写入，大大提高了写入性能。它已被用于许多键值存储中，例如 BigTable、LevelDB 和 RocksDB。

  基于LSM树的键值存储的内存组件，由MemTable和Immutable MemTable组成。 MemTable以仅追加模式存储最新的键值。当达到存储阈值时，Memtable 将转换为只读的 Immutable MemTable。基于LSM树的键值存储的磁盘或SSD部分由多个级别组成，每个级别由多个排序字符串表（SSTables）组成。每个级别都有大小限制，并且大小限制呈指数增长。当级别超过其大小限制时，将触发压缩操作，通过将 L i 中的 SSTable 合并到 Li +1 来将数据下推。

- ZenFS如何使RocksDB适应ZNS SSDs： ZenFS是西部数据公司开发的存储后端模块。它可以为新生成的 SSTable 分配区域，并从包含无效数据的区域回收可用空间。 ZenFS 采用经验方法（？）将 SSTable 放入区域中，由于区域中的 SSTable 可能具有不同的生命周期，因此区域内会产生许多无效数据。

  例如，当选择$L_2$中的SSTable来执行压缩，并且$L_3$ 中的所有SSTable都应该存储在$Zone_1$ 中，压缩后新生成的SSTable可以被写入到不同的Zone，例如$Zone_2$ 。因此，ZenFS 将生成包含具有不同生命周期的 SSTable的区域。这样一来，zone中的无效数据就不会被及时回收，增加了LSM-tree的空间放大。

  （图片来自ZenFS的Readme）

  

  <img src="https://user-images.githubusercontent.com/447288/84152469-fa3d6300-aa64-11ea-87c4-8a6653bb9d22.png" alt="zenfs stack" style="zoom:30%;" />

为了解决上述问题，在本文中，我们提出了一种用于 ZNS SSD 的新的节省空间的键值存储，称为 ZoneKV。 ZoneKV采用基于生命周期的区域存储模型和特定级别的区域分配算法，使每个区域中的SSTable具有相似的生命周期，从而比ZenFS具有更低的空间放大、更好的空间效率和更高的时间性能。简而言之，我们在本文中做出了以下贡献。

1. 为了解决ZNS SSD上LSM-tree的空间放大问题，ZoneKV提出了一种基于生命周期的区域存储模型，在一个区域中维护具有相似生命周期的SSTable，以减少空间放大并提高空间效率。
2. ZoneKV提出了一种特定于级别的区域分配算法来组织ZNS SSD中LSM树的级别。特别是，ZoneKV 将 L 0 和 L 1 放在一个区域中，因为这两个级别中的 SSTable 具有相似的生命周期。另外，ZoneKV将L i ( i ≥ 2)中的所有SSTable水平划分为切片，不同的切片存储在不同的zone中，使得每个zone的SSTable具有相同的生命周期。
3. 我们将 ZoneKV 与 RocksDB [12] 以及真实 ZNS SSD 上最先进的系统 ZenFS [1] 进行比较。与RocksDB相比，ZoneKV可以减轻约50%-60%的空间放大，与ZenFS相比，这一改进约为40%-50%。此外，ZoneKV 实现了最高的吞吐量。

## 2 相关工作

讨论了传统SSDs的局限性，ZNS SSDs可以作为一种改进的开放通道SSDs。

ZNS SSDs支持完整的存储堆栈，包括底层的块驱动程序到上层的文件系统。ZNS SSDs不执行设备侧的垃圾回收，意味着主机必须执行主机级别的垃圾回收。

为了尽量减少主机级的GC开销，最近的研究提出了一种新的ZNS接口ZNS+，以支持存储内部的区域压缩。专注于ZNS SSD上压缩的其他方法包括CAZA[16]和LL-压缩[17]。然而，这两种方法都会使得压缩后的SSTables散布在不同的区域中，从概念上讲，由同一压缩操作产生的SSTables应该具有相同的生命周期[5]。将它们放置在不同的区域中，对空间效率不友好。

到目前为止，据我们所知，ZenFS 是唯一将 RocksDB 适配到 ZNS SSD 的键值存储。但ZenFS并没有充分考虑SSTables的生命周期，也没有完整的GC逻辑。因此，具有不同生命周期的SSTables可能会存储在同一区域中，导致严重的空间放大。在本文中，我们主要关注改进ZenFS，并将ZenFS视为主要竞争对手。与 ZenFS 不同，我们建议将具有相似生命周期的 SSTable 存储在同一区域内，以减少 LSM 树的空间放大。

## 3 ZoneKV的设计

- 分析了现有方法的局限性，提出了ZoneKV的主要思想。
- 描述了ZoneKV的架构和关键技术，包括基于生命周期的区域存储和特定级别的区域分配。

### 3.1 现有方法的局限性

将RocksDB移植到ZNS SSD的基本方法是让RocksDB将SSTable存储到特定的区域，这是通过文件操作接口来实现的。虽然这种简单的实现可以支持 ZNS SSD 上的读/写操作，但它的空间利用率不高。这是因为 SSTable 随机分散在区域之间。由于每个zone中的SSTable可能有不同的生命周期，例如，一些SSTable经常更新，而另一些则从不更新，(?)

> 我们可以推断每个zone中会有很多无效数据，因为那些声明周期短的数据早就失效了，但ZNS SSD必须重置才能释放这些空间。

因此，如果所有SSTables都是随机存储在区域中的，那么每个区域中将会产生越来越多的无效数据，这会导致空间放大率高和空间浪费。

ZenFS  提出了一种改进的方法来在区域中存储SSTables。它为每个活跃区域维护最长的生命周期；如果新生成的SSTable的生命周期比活跃区域中的最长生命周期短，那么SSTable将被放入该区域中。与原始的RocksDB相比，ZenFS可以减少空间放大，但具有不同生命周期的SSTables可能仍然分布在同一个区域中。请注意，具有不同生命周期的SSTables具有不同的更新频率。因此，一个区域内的某些SSTables可能已经被更新，而其他SSTables则没有，这浪费了区域容量，且空间效率不高。

> ??说的好像SST会被就地更新一样,这个"更新指的是啥"

### 3.2  ZoneKV 的思想

在本文中，我们将 SSTable 的生命周期定义为它的创建时间和失效时间之间的间隔。假设 SSTable 在 t 1 创建，并在 t 2 压缩或更新；其生命周期定义为 | t 2 − t 1 | 。目标：将所有具有相似生命周期的 SSTable 存储到同一区域中。

获取 SSTable 的准确生命周期并不是一件容易的事。例如，当我们需要将 SSTable 写入 LSM 树中的某个级别时，我们只知道 SSTable 的创建时间。在 SSTable 被更新或压缩之前，我们不会知道它的失效时间。

我们不会显式维护每个 SSTable 的生命周期信息。相反，我们使用级别编号作为生命周期的指标。

**L0、L1：**RocksDB对L0**采用分层**（tiering compaction）压缩，这将使L0 中的所有SSTable失效，并将它们与L 1 中的SSTable合并，并产生新的SSTable，最终写入L 1 。因此，我们可以推断 L 0 中的所有 SSTable 具有相同的生命周期。另一方面，由于 L0 中 SSTable 的键范围重叠，因此在对 L0 进行分层压缩时，更有可能读取 L 1 中的所有 SSTable 并与 L 0 合并。因此，L1 中的几乎所有 SSTable 都会因 L 0 中触发的分层压缩而失效，这意味着 L 1 中的所有 SSTable 与 L 0 中的 SSTable 具有相似的生命周期。

**L>=2：**

此外，对于 L 2 和 L 3 等较低级别，RocksDB 使用 Leveling Compaction [12]，以循环方式选择 L i ( i ≥ 2) 中的一个 SSTable，并将该 SSTable 与 L_i +1中所有重叠的 SSTable 合并 。为此，我们可以看到具有小键的 SSTable 将首先被选择作为受害者进行压缩，这意味着它们具有相似的生命周期。因此，我们对 L i ( i ≥ 2) 中的 SSTables 进行水平分区，并将每个分区放在不同的区域中。

>RocksDB中tiering compaction 和  Leveling Compaction 压缩的区别：
>
>RocksDB是一种使用LSM树（Log-Structured Merge-tree）的键值存储，它通过将数据写入不同层级的结构来优化读写性能。在RocksDB中，数据首先写入内存中的MemTable，当MemTable满时，它会被转换成SSTable并写入磁盘的第0层（L0）。随后，这些SSTable会通过压缩（compaction）操作逐渐合并到更高层级。RocksDB提供了两种主要的压缩策略：Tiering Compaction和Leveling Compaction。这两种策略在处理SSTable合并和数据迁移方面有着根本的不同。
>
>### Tiering Compaction（分层压缩）
>
>- **特点**：在Tiering Compaction模式下，当一个层级（Level）的大小超过预定阈值时，新的SSTable会被合并到下一层级，但是不会与下一层级的SSTable立即合并。这意味着，每个层级可以包含多个SSTable文件，随着层级的增加，存储的SSTable也相应增加。
>- **优势**：减少了写放大（Write Amplification），因为它在合并时只是简单地将多个SSTable文件移动到下一个层级，而不是合并它们。这使得Tiering Compaction在写密集型应用中表现较好。
>- **劣势**：由于每个层级可能包含多个SSTable文件，这可能导致读放大（Read Amplification）增加，因为在查找数据时可能需要检查同一层级的多个SSTable。
>
>### Leveling Compaction（平层压缩）
>
>- **特点**：在Leveling Compaction模式下，当一个层级的数据量达到阈值时，该层级的所有SSTable会与下一层级的SSTable合并，并形成新的SSTable放入下一层级。这种策略确保了除了最顶层以外的每个层级最多只有一个SSTable文件。
>- **优势**：显著减少了读放大，因为在大多数情况下，每个层级只有一个SSTable文件，查找数据时不需要在多个文件间跳转。这使得Leveling Compaction在读密集型应用中表现更好。
>- **劣势**：由于需要合并整个层级的SSTable，这会导致更高的写放大，因为每次压缩都涉及到大量数据的复制和重写。
>
>### 选择
>
>选择哪种压缩策略取决于应用的具体需求：
>
>- 如果应用主要是写密集型的，并且可以容忍稍高的读延迟，那么Tiering Compaction可能是更好的选择。
>- 如果应用主要是读密集型的，并且需要优化读性能，那么Leveling Compaction会是更优的方案。
>
>RocksDB允许开发者根据具体的应用场景选择最适合的压缩策略，以达到最佳的存储效率和性能平衡。

小结:

**（1）基于生命周期的Zone Storage**。 ZoneKV建议在一个区域中维护具有相似寿命的SSTable，以减少空间放大并提高空间效率。 ZoneKV 不会显式维护每个 SSTable 的生命周期信息，而是使用每个 SSTable 的级别编号来隐式推断生命周期。这样的设计可以避免内存使用并维护生命周期信息的成本。

​    **(2)** **特定级别的区域分配。**首先，ZoneKV 建议将 L 0 和 L 1 放在一个区域中，因为这两个级别中的 SSTable 具有相似的生命周期。其次，ZoneKV将L i ( i ≥ 2)中的所有SSTable水平划分为切片，每个切片存储在一个zone中。

### 3.3 ZoneKV的架构

![image-20240325182729200](ZNS.assets/image-20240325182729200.png)

与 RocksDB 一样，ZoneKV 也包含内存组件和持久组件（即 ZNS SSD）。内存组件的作用与RocksDB相同，ZoneKV的独特设计侧重于持久化组件，它由两个方面组成。

- 首先，当SSTables写入特定级别时(无论是刷新操作或压缩操作，ZoneKV根据生命周期信息将SSTables写入特定区域（选择合适区域的算法将在第III-E节中讨论）
- 其次，LSM树中的每个级别都存储在不同的区域中，以使每个区域包含具有相似生命周期的SSTable。

如图1所示，ZoneKV将日志文件放在单独的区域中，因为日志以仅追加的方式写入并且从不更新；因此它们的寿命可以被认为是无限的。 

ZoneKV的实现是基于RocksDB的。与ZenFS[1]一样，ZoneKV修改了RocksDB中FileSystemWrapper类的接口，并通过libzbd[1]直接与区域交互。传统的磁盘I/O堆栈需要内核文件系统、块层、I/O调度层、块设备驱动层等一系列I/O子系统才能到达磁盘。这些长链总是会降低数据存储效率，间接降低磁盘吞吐量并增加请求延迟。 ZoneKV 针对 ZNS 进行了优化通过直接在 ZNS SSD 上执行端到端数据放置并绕过巨大的 I/O 堆栈。

### 3.4 基于时间的分区存储

ZoneKV提出了一种基于生命周期的区域存储模型，旨在减少空间放大并提高空间效率。在这个模型中，ZoneKV将具有相似生命周期的SSTables存储在同一区域（zone）中。这样做的目的是为了减少不同生命周期的SSTables分散在不同区域中，从而减少无效数据的产生和空间放大。

为了实现这一点，**ZoneKV并没有显式地维护每个SSTable的生命周期信息，而是使用SSTable的级别作为生命周期的隐式指示。**例如，L0和L1级别的SSTables被认为具有相似的生命周期，因此它们被存储在同一个区域中。对于L2和更高级别的SSTables，ZoneKV通过水平分区将它们分成多个片段，并将每个片段存储在不同的区域中，以确保每个区域中的SSTables具有相同的生命周期。

### 3.5 Level-Specific Zone Allocation（特定级别的区域分配）

ZoneKV并没有显式地维护每个SSTable的生命周期信息，而是使用SSTable的级别作为生命周期的隐式指示


具体来说，ZoneKV将日志文件的生命周期标记为-1，意味日志文件具有无限的生命周期；接下来，它将L0和L1级别的SSTables的生命周期设置为1；此外，对于Li（i ≥ 2）级别的SSTables，它们的生命周期被设置为i。



## 4 性能评估

- 描述了实验设置、写入性能、更新性能、读取性能、混合读写性能和多线程性能的测试。
- 展示了ZoneKV在各种工作负载和设置下的性能，特别是在减少空间放大和保持高吞吐量方面优于RocksDB和ZenFS。

## 5 总结

- 主要贡献，包括基于生命周期的区域存储和特定级别的区域分配，这些设计可以降低使用区域的数量并减少LSM-tree在ZNS SSDs上的空间放大。
- 强调了ZoneKV在多线程环境中的稳定和高性能。











# WALTZ (开源)

https://github.com/SNU-ARC/WALTZ VLDB'23

**摘要**

WALTZ 是一种基于 LSM 树的键值存储，它利用 ZNS SSD 的区域追加命令来提供紧凑的尾部延迟。

Lazy的元数据管理策略，允许在处理插入（put）查询时实现快速响应，减少在执行单个追加（append）命令时所需的锁定操作。不需要执行其他的同步操作来保证命令的执行。

文章使用了包括不同读/写比例和键偏斜的微基准测试（db_bench）以及现实的社交图工作负载（Facebook的MixGraph）。我们的评估显示，对于db_bench和MixGraph，尾延迟分别减少了2.19倍和2.45倍，最大减少幅度达到3.02倍和4.73倍。另外，由于消除了批量组写操作的开销，WALTZ还将查询吞吐量（QPS）提高了最多11.7%。



## 1 引言

高并发的put导致WAL开销很大。

> RocksDB batch-group 批量写

于是，RocksDB 引入了一个称为 batch-group writes  的过程，该过程在具有待处理 put 请求的多个 worker 中动态选择一个 leader 线程，收集所有剩余的记录，并让 leader 代表其他 worker 立即写入它们。



上述这种“bulk”写入是作为解决小规模写入效率低下的一个流行解决方案。通过合并多个小的写入请求为一个请求，可以显著提高数据处理的速度，然而，这样做可能加剧尾延迟。因为一个组内会共享最长的写入时间，特别是当某条记录大小较大时。（WAL entry是变长的）



介绍ZNS的出现；介绍ZenFS。

- 我们确定了尾延迟的主要原因：批处理组写入的同步开销，随着工作线程数量增加而导致键值存储中
- 我们是第一个提出利用 ZNS SSD 规范中新引入的追加命令来减少 WAL 记录的尾部延迟。
- 我们还引入了区域替换、保留和延迟元数据管理技术来高效处理并行追加。
- 我们使用真实的 ZNS SSD 设备作为后端存储在 RocksDB 上对 WALTZ 进行了原型设计，并使用 db_bench 微基准测试和 Facebook MixGraph 基准测试对其进行了评估。
- 评估表明 WALTZ 在极大地降低尾部延迟方面是有效的，最多可降低 4.73 倍，同时略微提高查询吞吐量。



## 2 背景

### 2.1 Log-Structured Merge (LSM) Tree

简要介绍了LSM-Tree，略。

写前日志（WAL）是处理PUT查询和确保数据持久性的重要机制。WAL的批量组写入，为了降低延迟，将多个PUT查询合并成批量进行写入。在批量组写过程中，领导线程负责收集并持久化合并的记录，确保数据的完整性和一致性。

### 2.2 Zoned Namespace (ZNS) SSD

此小节概述了ZNS SSD的基本特性。与传统SSD不同，ZNS SSD将存储空间划分为区域，只允许在每个区域内顺序写入。这简化了NAND闪存介质所需的闪存翻译层（FTL）的管理开销。文档详细说明了区域的特征，如每个区域都有一个从空、开放、关闭到满的状态，以及相关的写入规则和性能影响。



### 2.3 LSM Tree with ZNS SSD

这一部分探讨了LSM树与ZNS SSD结合的潜力，尤其是针对ZenFS的介绍。ZenFS是为ZNS SSD设计的一种文件系统插件，可以实现RocksDB的存储和管理。文档讨论了ZenFS的架构和优势，包括如何通过简化的文件结构和扩展管理来减少写放大和改善系统性能。

### 2.4 Overhead of Batch-Group Write

此节详述了批量组写操作的开销问题。尽管批量组写降低了存储资源管理的开销，但随着存储介质速度的提高，同步开销变得更加显著。文档解释了为什么随着线程数量的增加，同步开销也会增加，并讨论了这一问题如何影响尾延迟。同时也展示了一些实验数据，揭示了不同线程数量下的写延迟分布情况。

这部分为WALTZ的设计和实现提供了技术背景和理论基础，说明了为什么选择特定技术方案来优化ZNS SSD上的LSM树性能。



## WALTZ设计与实现

### 总览

![image-20240512161637568](ZNS.assets/image-20240512161637568.png)

图 6 展示了 WALTZ 的整体结构。它包括替换检查器（Replacement Checker）和区域管理器（Zone Manager）以及两个队列用于彼此通信。

替换检查器确定何时替换 WAL 文件的当前活动区域，并在活动区域应该被替换时通知处理相应 PUT 查询的工作线程（即，关闭当前活动区域并打开一个新区域）。为了快速管理替换的区域，替换检查器使用了一个虚拟追加（dummy append），其速度比使用区域报告命令查找当前区域的确切写指针要快得多。

区域管理器负责预留新的空区域，以便在工作线程请求为 WAL 文件提供新的区域时更加高效地提供，而不是使用 ZenFS 的基线区域分配机制。此外，区域管理器接管了正在关闭的区域的区域结束和关闭操作。这些操作在基线实现中需要花费大量时间，占据了工作线程的写入尾延迟的主要部分。

### WALTZ的设计

**写入路径。**WALTZ 的写入路径比原始的 RocksDB 更简单、更轻量。RocksDB 通过调用 JoinBatchGroup() 来执行领导者选举，领导者从跟随者那里收集记录，并通过调用 Enter/ExitAsBatchGroupLeader() 来使它们持久化；然而，WALTZ 绕过了这一部分。相反，所有工作线程都请求将它们的记录追加到 WAL 文件中。一旦完成这个操作，工作线程立即开始更新 MemTable，而不用担心其他工作线程的状态。

> 直接取消了批量写

**替换检查器。**(根据Apped LBA主动检查Zone是否将要写满)

如果一个区域已满，追加命令将引发失败响应。在这种情况下，会触发重试，其延迟会增加尾延迟。相反，我们建议防止重试发生。在执行追加操作后，WALTZ 根据返回的 ALBA(Apped LBA) 计算剩余空间，并在活动区域的剩余空间低于阈值时（例如，低于区域空间的 1%）主动启动区域替换。如果将此阈值设置得太高，则会浪费区域空间，从而提高 WAF 值，但可以减少增加尾延迟的可能性。

这样，我们在 WALTZ 中集成了一种低成本的保护机制，以防止多个工作线程同时尝试执行区域替换。与基线 RocksDB 相比，在基线 RocksDB 中，现有的批处理组写入总是经过昂贵的领导者选举阶段，WALTZ 的保护开销可以忽略不计，因为这仅在活动区域的剩余空间低于阈值时发生。在替换线程进行区域替换时，其他工作线程可以继续将它们的记录追加到当前区域的剩余空间，从而最大程度地减少阻塞时间。如果区域替换任务花费很长时间，直到当前区域的空间耗尽时仍未完成，将引发区域 FULL 的失败响应。在这种情况下，等替换任务完成后，再重试追加操作。一旦分配了新的区域，替换的区域的范围信息必须存储在 ZoneFile 的范围列表中。然而，由于在替换线程执行区域替换时，其他线程可能已经追加了它们的记录，替换线程收到的 ALBA 可能不会精确地匹配实际范围中写入的数据的最后位置。为了解决这个问题，在分配了新的区域后，替换线程通过追加命令将虚拟数据发送到替换的区域，然后检查完成条目的状态码和 ALBA 字段。如果返回了区域满状态码，则意味着该区域的最后一个扇区包含当前 WAL 文件的有效数据，因此我们使用该区域的最后 LBA 来计算范围的大小。如果追加命令成功，则由虚拟追加返回的 ALBA 是虚拟数据存储位置，我们可以确定区域直到返回的 ALBA 位置的数据是 WAL 文件的有效数据。基于 ALBA 计算范围大小。 



**虚拟追加。**为什么虚拟追加优先于区域报告命令来检索最新的区域写指针，原因在于其较低的开销。单个区域的区域报告命令的平均延迟为 6687 微秒，对于替换线程来说，这太长了，无法在处理其他线程的 put 查询时解析。然而，区域追加命令显示出更快的速度，在单线程环境中平均约为 93 微秒。由于此过程在替换线程将新区域注册为活动区域后单独运行，其他工作线程现在执行 WAL 记录追加到新的活动区域。因此，替换线程几乎总是唯一访问替换区域的线程，使虚拟追加更快。然而，即使假设其他工作线程仍在追加到替换区域的剩余空间，追加命令的最差性能（例如，多线程，尾延迟情况）仍然比区域报告命令快得多（见图 3）。此外，由于后台线程使用区域结束命令使剩余空间无效，因此虚拟追加命令仅提前使一个扇区无效，不会产生额外的开销。



**区域分配与区域管理器。**区域替换过程可能会增加负责替换的线程（替换线程）的写入尾延迟。让我们首先回顾现有工作存在的问题，然后提出我们的方法。在 ZenFS [7] 中，进行区域分配时，它会获取 I/O 区域互斥锁，并在执行分配时遍历所有区域，考虑区域的剩余空间和寿命。在分配阶段，剩余空间低于指定阈值的区域将被完成。然后，如果存储在此区域中的第一个文件的 WLTH（写入生命周期）长于请求进行区域分配的文件的 WLTH，则 ZenFS 尝试分配该区域。因此，在需要管理多个区域（例如，区域完成）或者其他后台线程尝试分配区域并持有 I/O 区域互斥锁以创建新的 SST 文件时，区域分配可能会意外延迟。此外，由于对 I/O 区域进行全面迭代的实现，随着区域数量的增加，区域分配循环的迭代开销增加，限制了可扩展性。在小尺寸区域 ZNS 情况下，这个问题更加严重，它提供了更细粒度控制单个设备的特性。即使在相同容量的 NAND 闪存介质上，它也会暴露出小尺寸区域，使得区域数量远远多于大尺寸区域 ZNS SSD，因此迭代的循环开销增加了几倍，尾延迟受到不利影响。为了最小化这种开销，我们添加了运行在后台线程上的区域管理器，以预留两个区域以立即响应 WAL 文件的区域替换情况。预留两个区域的主要原因是，在 MemTable 切换过程中会出现两个 WAL 文件临时可用且同时被写入的情况。区域管理器的一个主要作用是预留上述的 WAL 区域。此外，区域管理器还负责完成和关闭替换的区域。从 WAL 文件替换的区域处于 OPEN 或 FULL 状态，取决于剩余容量的存在与否。当进入 FULL 状态时，ZNS SSD 的内部资源已经释放，且 open_zone_limit 未被占用。但是，如果还有剩余空间且区域处于 OPEN 状态，则 open_zone_limit 被占用。因此，如果没有对资源饥饿进行管理，则无法充分利用 ZNS SSD。因此，我们不仅执行 WAL 区域分配，还对替换的区域进行状态检查，并在后台处理完成和关闭区域。基于此，替换线程在处理 put 查询时通过区域管理器接收一个区域。在将其注册到 ZoneFile 的活动区域之后，替换线程将替换的区域传递到 done_queue。它可以快速响应，而不用担心替换区域的后续处理，从而极大地减少了尾延迟。区域管理器执行替换区域的剩余处理，监视 done_queue 并在后台处理它。

**懒惰的 ZoneFile 元数据管理。**ZenFS 的 ZoneFile 中管理了几种文件元数据，如活动区域、范围列表、文件大小、写指针、容量等。由于活动区域是其他工作线程尝试追加 WAL 记录的地方，因此活动区域替换应立即执行。此外，范围列表中存储的范围的顺序很重要，因为它决定了存储在 ZoneFile 中的数据位置，这使得懒更新更加困难。其他元数据元素，如文件大小、活动区域的写指针和容量，在写路径中并不关键。在 ZenFS 的写入情况下，对每个 ZoneFile 进行了同步保证，因此不需要对这些元素进行额外的保护。然而，在我们的并行追加架构中，ZoneFile 可以同时由请求 put 查询的工作线程追加，因此需要额外的保护。我们应用懒更新，替换了原有的在每次追加时管理非关键 ZoneFile 元数据的方法，以避免同步并支持对 put 查询的快速响应。相反，根据虚拟追加返回的 ALBA，WALTZ 计算文件大小、区域剩余容量和最新的写指针，并在区域替换期间一次性更新 ZoneFile 元数据。



**恢复。**原始的 RocksDB 在写入阶段为每个键值对或写入批次分配一个序列号，根据数据库配置。我们确定了批处理组写入过程的开销，并提出了一个并行追加架构来加速并发 put 查询中的 WAL 写入。然而，即使有了这个结构，WAL 追加的最小单位仍然是一个写入批次，因此不会影响 RocksDB 的序列号结构。ZenFS 提供了一个通过 Fsync() 函数永久同步文件的接口，该函数在每次 WAL 记录写入时被调用。当调用 Fsync() 时，ZenFS 将更新信息写入 ZenMetaLog 以供未来恢复使用。因此，WAL 记录主要由 ZenFS 恢复，而 RocksDB 可以从单独的记录中恢复写入批次或键值对。然而，在 WALTZ 中，由于懒惰的元数据更新架构，仅当活动区域被替换时才会记录 WAL 文件的元数据，而不是在每次 WAL 追加时更新元数据。因此，在故障恢复点，只有最后一个活动区域的分配和起始点的写指针信息保留下来，而追加到区域的 WAL 数据的总大小没有记录。为了解决这个问题，在恢复阶段，我们使用虚拟追加方法来确定活动区域的当前写指针，并将返回的写指针视为存储在此 WAL 文件中的有效记录的最后位置。这是因为当 ZenFS 为 ZoneFile 分配一个活动区域时，它提供了单独的保护，以防止另一个 ZoneFile 占用同一区域。因此，从活动区域的起始点开始的所有数据都保证源自恢复的 WAL 文件。至于对恢复时间的影响，我们的设计应恢复最多两个 WAL 文件的写指针，如果在 MemTable 切换时发生断电，这是最坏的情况。因此，对于 WALTZ 增加的恢复开销最多是两个虚拟追加操作的平均延迟约为 93 微秒。由于在恢复时禁用了主机写入，因此不存在资源争用。因此，WALTZ 的恢复时间增加最多约为 200 微秒，可以忽略不计。

![image-20240512164245216](ZNS.assets/image-20240512164245216.png)

**实现。**我们在 RocksDB v6.25.3 上实现了 WALTZ，使用 ZenFS v1.0.2 插件以支持 ZNS。ZenFS 使用 libzbd [15] 库来管理 ZNS SSD，但是该库不支持追加命令。我们将英特尔存储性能开发工具包（SPDK）[14] v22.01.2 移植到 ZenFS 上，以支持追加命令。WALTZ 总共需要 1600 行代码（LOC）— 大约 700 行 LOC 用于将英特尔 SPDK 附加到 ZenFS，剩余的约 900 行 LOC 用于其他实现部分。

示例中的 Put 查询步骤 图 7(a) 展示了一个 put 查询的示例步骤。当收到一个 put 请求时，首先将其写入 WAL 文件 1 。我们找到在 WAL 文件中注册的活动区域，并向该区域发出追加命令 2 。在执行追加后，我们从完成条目中检索 ALBA，并将其传递给 Replacement Checker 3 。Replacement Checker 根据 ALBA 计算活动区域的剩余空间，如果剩余空间足够，则直接进入 MemTable 插入阶段 4 。 图 7(b) 展示了区域替换情况。如果 Replacement Checker 检测到追加命令的失败，或者根据 ALBA 计算出的剩余空间小于指定的阈值，则会触发替换过程。首先，我们从 Zone Manager 中检索一个新的区域 4，并将分配的区域注册为 WAL 文件的新活动区域 5 。然后，我们进行虚拟追加 6 来检查替换区域的有效区域。如果虚拟追加失败，则根据替换区域的末尾 LBA 计算范围大小；如果成功，则根据虚拟追加返回的 ALBA 计算范围大小 。最后，工作线程可以继续进行 MemTable 插入阶段 8 。





# FAST'24涉及ZNS的文章：

1. I/O Passthru: Upstreaming a flexible and efficient I/O Path in Linux
2. RFUSE: Modernizing Userspace Filesystem Framework through Scalable Kernel-Userspace Communication
3. MIDAS: Minimizing Write Amplification in Log-Structured Systems through Adaptive Group Number and Size Configuration 
4. The Design and Implementation of a Capacity-Variant Storage System





# CVSS：避免SSD性能骤降

The Design and Implementation of a Capacity-Variant Storage System

https://www.usenix.org/conference/fast24/presentation/jiao

我们介绍了一种针对基于闪存的固态硬盘（SSD）的容量可变存储系统（CVSS）的设计与实现。CVSS旨在通过允许存储容量随时间优雅减少，从而在整个SSD的生命周期内维持高性能，防止出现性能逐渐下降的症状。CVSS包含三个关键组件：

- CV-SSD，一种最小化写入放大并随年龄增长优雅减少其导出容量的SSD；
- CV-FS，一种用于弹性逻辑分区的日志结构文件系统
- CV-manager，一种基于存储系统状态协调系统组件的用户级程序。

我们通过合成和真实工作负载证明了CVSS的有效性，并展示了与固定容量存储系统相比，在延迟、吞吐量和寿命方面的显著改进。具体来说，在真实工作负载下，CVSS将延迟降低，吞吐量提高，并分别延长寿命8-53%，49-316%和268-327%。



### 1. 引言

> Fail-slow 问题

近期，针对基于SSD的性能逐渐下降症状（fail-slow）获得了显著关注。在SSD中，这种退化通常是由于SSD内部逻辑尝试纠正错误所引起的。最近的研究表明，性能逐渐下降的驱动器可能会导致高达3.65倍的延迟峰值，并且由于闪存的可靠性随时间持续恶化，我们预计性能逐渐下降症状对整体系统性能的影响将会增加。



### 2. 背景与动机

详细介绍了CVSS的动机，解释了SSD中闪存错误和磨损趋势的增加。批判了当前固定容量存储系统模型加剧了与可靠性相关的性能下降问题，并回顾了以往尝试解决这些问题的努力。



### 3. 容量变化的设计

设计部分概述了一项高级原则，即放宽存储设备的固定容量抽象，允许在容量、性能和可靠性之间进行权衡。介绍了CVSS的三个关键组件：CV-FS支持弹性逻辑分区，CV-SSD通过映射出错误倾向的块来维护设备性能，CV-manager协调容量变化系统。

### 4. 实现

提供了实现CVSS的细节，包括对Linux内核的修改以支持容量变化，对F2FS的更改以解决容量变化触发的重映射问题，以及对FEMU（一个闪存模拟器）的增强以模拟CV-SSD的行为。这些修改旨在支持一个能够根据磨损和错误动态调整其存储容量的系统。



**3 容量可变设计** 容量可变系统背后的高级设计原则在图3中有所说明。该系统放宽了存储设备的固定容量抽象，并使得在容量、性能和可靠性之间实现更好的权衡成为可能。传统的固定容量接口，其设计初衷是用于硬盘驱动器（HDD），假定所有存储组件要么同时工作要么同时失败。然而，这一假设对于SSD并不准确，因为闪存块是故障的基本单位，映射出失败、不良和老化块是FTL的责任。





### 5. 容量变化的评估

评估部分讨论了测试CVSS在各种工作负载下的实验设置、方法和结果。它证明了CVSS在降低延迟、提高吞吐量和延长SSD寿命方面的有效性，与传统的固定容量存储系统相比。



### 6. 讨论与未来工作

讨论部分涉及容量变化的不同用例，包括其在ZNS（区域命名空间）SSD和RAID系统中的应用。概述了CVSS在简化SSD设计、改善数据中心存储管理和延长桌面SSD使用寿命方面的潜在好处。



### 7. 总结

结论再次确认采用容量变化方法的优势，强调其在减轻固定容量SSD固有限制方面的作用，尤其是关于耐用性和随时间性能。容量变化系统被定位为固定容量SSD限制的一个实用解决方案，承诺将进行持续的优化和特性开发。







# ZenFS+

在本文中，我们提出了ZenFS+，这是RocksDB的一个新型存储后端，专为小区域分区命名空间（ZNS）SSD设计。RocksDB具有复杂的内部操作，如刷新（flush）和压缩（compaction），它们在不同线程中运行，并以其对sstables的影响而闻名。由于刷新和压缩之间的并发存储I/O，ZenFS在小区域ZNS SSD上呈现出不令人满意的性能。我们相信，ZenFS+展示了ZNS SSD如何支持现代键值存储的性能和隔离性。利用ZNS SSD，ZenFS+智能地识别独立区域组（IZG），揭示了设备的内部并行性。有了IZG信息，ZenFS+有效地将RocksDB的刷新工作负载与压缩隔离开来。此外，ZenFS+将sstables分散到多个IZGs，使存储写入能够利用硬件并行性。ZenFS+在写入密集型微基准测试中展示了高达4.8倍的存储吞吐量，并稳定了99.9P尾部延迟，将现有ZenFS的延迟降低了51倍。此外，ZenFS+实现了主动垃圾回收，并在设备寿命更长的时间内展示了可持续的性能。
关键词包括：数据存储系统、闪存存储器、并行架构、存储管理、系统软件。

**I. 引言**
键值存储是现代大数据系统的基本组成部分。在强大的存储引擎的帮助下，Google、Facebook、Twitter和Amazon等公司能够及时处理大量非结构化数据。最近的一份报告表明，Amazon的云键值存储配置了高可用性，每秒可处理6820万次请求，这显示了体面的大型数据系统的处理查询需求，具有显著的I/O吞吐量和小延迟。
RocksDB是由Facebook开发的一款开源键值存储[2]，[3]。它在社交图分析[2]、分布式文件系统[2]、结构化/非结构化数据库[4]等研究和工业项目中得到了广泛应用。RocksDB之所以在大规模大数据系统中流行，是因为它通过并发线程提高了写入性能。写入性能至关重要，因为这些系统中不断涌入大量数据，键值存储（KVS）需要在有限的时间预算内处理密集的‘PUT’请求。此外，数据库的最近性对于保持输入数据的新鲜度至关重要。

**II. 背景**
在本节中，我们首先解释了基于LSM树的键值存储（KVS）的结构及其内部操作，包括刷新和压缩。然后，我们讨论了传统SSD的问题以及ZNS SSD如何解决这些问题。

**III. 动机：ZNS SSD的承诺破裂**
ZNS SSD声称比传统SSD有优势。声称的好处包括1）ZNS SSD提供了稳定的延迟和带宽，因为ZNS SSD去除了使用FTL的语义差距，2）ZNS SSD通过减少垃圾回收和超额配置来最小化块接口税。本节展示了在RocksDB上使用ZNS SSD的一些实验，说明了ZenFS+的动机案例。我们的问题是在单个KVS应用程序中，刷新和压缩之间的性能干扰在ZNS SSD中有多大。

**IV. 设计**
鉴于上一节的观察，小区域ZNS SSD需要更多的考虑以获得更好的性能和隔离。因此，本节介绍了ZenFS+的设计。

**V. 评估**
A. ZenFS+在fill random工作负载下的性能和隔离
我们在不同的配置下评估了ZenFS+在RocksDB基准测试中的性能。我们的实验硬件和软件配置与第III节中的相同。

**VI. 讨论**
ZNS SSD和任何其他SSD一样，有几个硬件设计参数。区域数量、区域大小、通道和路径数量、块中页面数量等。围绕ZenFS+的一个担忧是该设计是否适用于大区域ZNS SSD。例如，大区域ZNS SSD设备可以轻松获得写入性能而不需要sstables条带化。ZenFS+智能地识别IZG信息；因此，ZenFS+为大区域ZNS SSD设备配置了单个IZG。在这种情况下，它本质上将sstable条带宽度限制为1，并且可以与ZenFS设置兼容。目前，ZenFS+假设小区域ZNS SSD是大区域ZNS SSD的替代品，因为小区域ZNS SSD在并发工作负载下的性能隔离方面具有显著的好处。同时请注意，大区域ZNS SSD在软件方面难以实现性能隔离，因为它不允许从软件侧控制内部并行性。换句话说，它在软件设计方面提供了更多的自由度，考虑到区域分配和细粒度的垃圾回收。

**VII. 相关工作**
有关RocksDB的研究有很多。首先，Siying等人介绍了在实际系统中开发RocksDB的广泛经验[3]。它介绍了RocksDB如何不断发展和优化各个方面的性能，包括写入/空间放大、数据格式和压缩、向后兼容性、备份和数据损坏处理以及在多RocksDB实例下的可扩展性。

**VIII. 结论**
本文提出了一种使用ZNS SSD的新型KVS方法。通过扩展ZenFS，我们提出了ZenFS+。ZenFS+展示了ZNS SSD如何支持现代KVS的性能和隔离性。ZenFS+智能地区分独立区域组，并从压缩中隔离刷新性能。因此，刷新为写入密集型工作负载提供了更稳定的带宽和延迟。在我们的实验中，ZenFS+将99.9P尾部延迟降低了51倍。此外，ZenFS+利用IZG信息利用设备的内部并行性。通过条纹化sstable，ZenFS+在微基准测试中实现了高达4.8倍的刷新吞吐量和2.6倍的应用程序吞吐量，并在宏观基准测试中实现了约两倍的吞吐量，与当前的ZenFS实现相比。我们进一步实现了主动垃圾回收，这是当前ZenFS中缺失的部分，使其在现实世界系统中更具可持续性。



# ZWAL

erosys23 workshop

- 基于simpleZNSdevice(他自己封装的)
  - spdk
  - io_uring

https://github.com/stonet-research/zwal

**摘要**

KV存储是广泛使用的数据库，需要性能稳定性。分区命名空间（Zoned Namespace，ZNS）是一种新兴的闪存存储设备接口，提供了这种稳定性。由于LSM树中的顺序写访问模式是KV存储中普遍存在的数据结构，因此适合采用仅追加的ZNS接口。然而，LSM树在ZNS上实现的写入吞吐量有限**。这种限制是因为LSM树写入的最大部分是针对LSM树的写前日志（WAL）组件的小写入**，而ZNS对小写入I/O的性能有限。

ZNS特定的区追加操作提供了一种解决方案，增强了小顺序写入的吞吐量。可见，Zone Append命令有很好的并行性，有效增强了小文件顺序写入的吞吐量。有希望能够解决高并发小文件（例如上文的WAL）的写入瓶颈问题。然而，使用Append命令仍需克服一个问题，由于Append需要在响应中才返回地址，也就是说，同时到达的写入命令的实际写入顺序是由设备决定的，可能与命令实际发出的顺序相违背，实际存储的是乱序结果。于是，我们通过为每个追加操作添加标识符以及一种新颖的恢复技术来解决这种重排序问题。



## 引言



![image-20240512034150896](ZNS.assets/image-20240512034150896.png)

我们在图1中可视化了LSM树的PUT操作。为了确保MemTable在关闭时不会丢失数据，LSM树将PUT操作写入存储上的一个称为写前日志（WAL）的日志中。WAL记录了随时间发生的所有KV对更改。当KV存储重新启动时，LSM树通过一种称为WAL恢复的过程来恢复其状态。

尽管 ZNS 实现了稳定的 LSM 树吞吐量，但对于 LSM 树的 WAL 组件，它导致了显著的写入吞吐量挑战。ZNS 禁止应用程序同时向同一区域发出写入 I/O。这是因为 (1) 写入 I/O 需要发出到区域的顺序地址 (顺序只写区域)，以及 (2) SSD 可以自由重新排序 I/O 请求。因此，对 WAL 的 PUT 操作是串行化的，仅限制了 WAL 的吞吐量，因为只能同时处理一个 PUT。

**利用Append命令优化WAL的写入**，主要挑战在于区域追加是发出到一个区域而不是一个地址的，并且仅在完成时返回它们的地址。这个地址可以在区域的任何地方，因此 SSD 可以重新排序 WAL 数据。因此，WAL 需要对数据重新排序具有抵抗性。因此，目前 ZNS 上的 WAL 设计（例如 RocksDB + ZenFS）只使用写入 I/O，或者通过增加线程来扩展区域追加。我们在图 1 中将重新排序挑战可视化为“?”。



这项工作提出了ZWALs（Zone Append-friendly Write-Ahead Logs），它是针对ZNS（Zoned Namespace SSD）设计的一种适用于区域追加的WAL（Write-Ahead Logging）机制。为每个 PUT 请求添加 64 位原子递增的序列号来实现，用于推断 WAL 内部的顺序。在恢复过程中，WAL 读取所有的 KV 对更改，然后使用序列号将它们重新排序为它们的原始顺序。排序后，LSM 树按顺序应用更改。考虑到 LSM 树 WAL 通常只在数据库启动期间恢复，并且 WAL 很小（例如，32 MiB），我们认为在读取 WAL 方面进行一些牺牲以换取更好的写入吞吐量是可以接受的。为了减少重新排序的开销，并防止读取整个 WAL，引入了 WAL 屏障的概念，确保处同步所有的区域追加。障碍确保对 WAL 的读取只需要在连续的障碍之间读取和排序，从而提高了 WAL 的读取性能。（不就是检查点？）



我们在 ZenFS 中实现了 ZWALs，这是 RocksDB 的最新自定义文件系统后端，报告称 ZWAL 比传统 WAL 在商用可用的 ZNS SSD 上实现了显著更高的写入吞吐量，YCSB 基准测试套件上高达 33.02% 的提高。类似地，我们在 ConfZNS [33] 模拟器上重复了我们的实验，并报告说在高内部并行性的情况下，ZWAL 在 YCSB 上可以提供高达 8.56 倍的写入吞吐量。在本文中，我们做出了以下关键贡献：

1. 我们表征了区域追加操作的性能，并解释了我们如何利用它们进行 WAL。
2. 我们设计并实现了 ZWALs——一种适用于 ZNS 区域追加的新 WAL 设计。
3. 我们在微观和宏观层面上评估了 ZWALs。
4. 我们将我们的 ZWAL 实现代码开源在 https://github.com/stonet-research/zwal。



##   动机：为什么使用区追加？

小实验：对比 write和append。  修改了FIO(v3.32)、使用io_uring + NVMe 通路，（Linux 块层不支持append）// We modify fio to support zone appends for passthrough (∼10 LOC).



![image-20240512043216204](ZNS.assets/image-20240512043216204.png)



我们通过增加队列深度（QD）——最大并发区域追加数量——来评估区域追加的并发性，并以每秒 I/O 操作数（IOPS）来衡量吞吐量。由于 ZNS 禁止多个写入 I/O 到同一区域，我们只评估 QD 为 1 时的写入 I/O。我们以 8 KiB 的粒度发出所有请求，这被评估为最佳请求大小（即，最低请求延迟）。图 2a 显示了随着 QD 的增加（x 轴），区域追加的吞吐量（y 轴，越高越好）的变化。区域追加可扩展到 QD 为 4，此后达到设备的峰值带宽，根据设备的规格表。我们观察到，在高 QD 下，区域追加的写入吞吐量比写入 I/O 高出多达 2.41 倍。在 QD 为 1 时，写入 I/O 导致更高的吞吐量（10.01%）。我们还研究了请求大小对区域追加和写入吞吐量之间差异的影响。虽然写入 WAL 的写入很小，但是像 ZenFS 这样的最新文件系统会缓冲写入，导致大型周期性写入（例如，1 MiB）。结果（未显示）显示，对于较大的请求（32 KiB 及以上），在任何 QD 下，写入和区域追加的吞吐量相似。简而言之，对于小的顺序写入，区域追加比写入 I/O 具有更高的写入并发性和吞吐量（确认 [11]）。



 我们通过增加队列深度（QD）——最大并发区追加数，来评估区追加的并发性，并以I/O操作每秒（IOPS）来测量吞吐量。

我们以8 KiB的粒度发出所有请求，我们将其评估为最佳请求大小（即，最低请求延迟）。

区追加可以扩展到QD为4，在此之后达到设备的峰值带宽，根据设备的规格表。我们观察到，在高QD时，区追加的写入吞吐量高达写入I/O的2.41倍。在QD为1时，写入I/O导致较高的吞吐量（10.01%）。

**此外，**我们观察到，对于较大的请求大小，区追加和写入的性能相似。虽然对WAL的写入是小的，但诸如ZenFS等最先进的文件系统会缓冲写入，导致周期性大型写入（例如，1 MiB）。结果（未显示）显示，对于较大的请求（32 KiB及以上），在任何QD下，写入和区追加的吞吐量相似。简而言之，对于小的顺序写入，区追加比写入I/O具有更高的写入并发性和吞吐量（验证了[11]）。 我们的工作面向区域内并行性高的SSD（即，区域内并行性）。我们评估的商用SSD可扩展到QD 4，我们还使用模拟器ConfZNS [33]探索了具有更高区域内并行性的ZNS的配置空间。我们将模拟的SSD定制为高区域内并行性（源代码中的确切配置）。在所有进一步的实验中（除非明确说明），我们使用这个模拟的SSD。图2b显示了此SSD的8 KiB区追加的吞吐量。在此SSD上，区追加可扩展到QD 32。对于较大的请求大小，我们观察到写入I/O和区追加的性能相似。

总之，对于小请求大小和高QD，区追加导致更高的写入吞吐量和并发性。因此，我们建议对于频繁发出小写入的应用程序，例如WALs，使用区追加。



## ZWAL的设计和实现

在本节中，我们详细介绍了ZWAL的设计和实现。首先，我们解释了ZWAL的设计目标及其与传统WAL的设计差异。其次，我们解释了如何在ZenFS文件系统中实现ZWAL。 

### ZWAL设计

我们设计了ZWALs 一种适用于ZNS SSD的新型WAL。当然，这种设计不限于LSM树，也适用于其他数据库，如SQLite [15]。此外，它适用于任何重新排序写入请求的存储介质/接口。然而，我们将讨论限制在ZNS上的LSM树，并使用ZenFS作为参考模型，以解释我们如何为ZNS更改现有的WAL设计（在第6节中更多介绍）。我们的ZWAL设计围绕着三个关键的WAL特性展开：

（1）WALs是写入密集型的，并主要发出小写入；

（2）WALs仅在数据库恢复期间读取；

（3）WALs通常很小（即，64 MiB [14]）

WAL的性能受到对WAL的小写入限制，但读取只是偶尔发生。因此，我们认为以降低读取性能为代价来增加写入性能是可以接受的。我们的设计目标是提高写入性能，并匹配区追加的峰值性能（见第2节）。在WAL中，我们区分四个主要操作：**写入WAL，从WAL中恢复所有数据，分配WAL和删除WAL**。我们使用图3来解释ZWAL的设计，图3代表了ZWAL的设计。 

> wal entry = seqnum + size + k-v

![image-20240512050929140](ZNS.assets/image-20240512050929140.png)

**WAL写入**在WAL写入时，PUT请求的数据被写入WAL的末尾，然后触发Zone写指针的写入I/O。如果同时发出了另一个PUT操作，则必须等待前一个PUT完成。为了增加并发性，ZWALs会向区域（的头部？）发出区追加，而不等待区追加完成。这样，多个PUT操作可以同时写入WAL。但并发区追加会导致乱序，无法保证PUT请求的顺序。

所以，ZWAL通过在每个WAL写入之前添加一个报头（128位的header）来实现重排序。我们将WAL数据和头部（黄色）组合成一个WAL entry。**这个报头由64位序列号和WAL entry的大小组成。**序列号以原子方式增加，并表示绝对数据顺序。每个WAL维护自己的序列号以避免翻转的风险（WAL不太可能是2的64次方页）；条目的大小用于推断后续追加的 WAL 条目（如果有）的位置。**为啥要保存entry的大小？**如果使用区域追加返回的地址来确定数据存储的位置，这个返回地址是易失的，还需要另一个写操作将此地址存储到存储器中。

此外，追加操作的理想请求大小可能与页面大小不同，并且 KV 对可能明显小于page size。因此，ZWAL 的允许进行缓冲（类似于 ZenFS）。在写入 WAL 时，WAL 首先将数据复制到缓冲区。一旦缓冲区满了或者 WAL 已经同步（例如，fsync、close），我们使用区域追加将数据写入 SSD。

需要注意的是，无论缓冲区大小如何，ZNS 都不允许区域追加跨越区域边界。如果一个区域追加请求跨越了边界，ZWAL 会将请求拆分成两部分，分别发送到每个区域，并分配各自的序列号。

**WAL恢复**

WAL 恢复。在 WAL 恢复过程中，LSM 树会顺序扫描其 WAL，并将读取的数据应用到其内存表中。LSM 树每次读取几 KB 数据。然而，ZWAL 存储在 SSD 上是无序的；ZWAL 需要恢复其原始顺序。ZWAL 通过创建从逻辑地址（即偏移量）到物理地址的映射来实现这一点。

> 下面这段不知道在说啥

在读取时，它首先找到与逻辑地址对应的 WAL 条目。它使用 WAL 报头中的信息找到这个条目。由于序列号是单调递增的，并且数据只追加到 WAL 中，具有更高序列号的 WAL 条目具有严格更高的逻辑地址。具体来说，具有序列号 x 的 WAL 条目的逻辑地址等于序列号为 x-1 的 WAL 条目的逻辑地址加上其大小。例如，具有序列号 1 的 PUT 存储在 PUT 0 的逻辑地址加上 PUT 0 的大小处。在对 WAL 进行读取时，ZWAL 会读取具有相应逻辑地址的条目。

然而，检索WAL头部是具有挑战性的。因为每个WAL条目的大小可能不同，ZWAL无法预先确定WAL头部的位置，除非是第一个请求。因此，ZWAL需要顺序扫描整个WAL，逐个条目地查找WAL头部。一种替代解决方案是仅读取一次WAL并在内存中保持逻辑地址的映射，但这需要与WAL大小成比例的内存。因此，ZWAL采用了一种更高效的方案：使用屏障。ZWAL在预定义的页面间隔（称为Pbarrier）插入屏障。在屏障处，ZWAL同步所有区域追加操作（即等待所有操作完成）。请求在连续的屏障之间进行排序，即屏障之后的追加操作的物理地址严格高于屏障之前的追加操作。在读取过程中，ZWAL首先找到最近的屏障，然后读取两个屏障之间的所有数据。然后，ZWAL根据序列号创建WAL条目的映射，并根据序列号对映射进行排序。通过这种设计，ZWAL每次只需要读取和维护一个页面间隔的映射，从而将I/O和内存占用限制在可配置的上限内。此外，该映射还可以进行缓存，因为读取是顺序的，并且后续读取很可能出现在同一个屏障内。根据设计，预期ZWAL的恢复成本略高于传统WAL，并且与屏障大小成比例（对于排序为O（n log n））

**WAL的分配**

在ZenFS中，这涉及将一个区域（zone）分配给WAL。这个区域并不专门用于WAL，而是可以与其他LSM-tree组件共享。但是，ZWAL有更严格的限制，它需要为WAL专门分配区域。

这是因为两个原因：首先，为了防止其他LSM-tree组件向与区域追加（zone appends）相同的区域发出写入请求，因为这会导致区域追加需要等待写入完成，从而失去了优势。其次，ZWAL的恢复过程要求所有WAL数据都要连续存储，因此需要专门的区域来确保数据的连续性。

**WAL的删除**

关于WAL的删除（deletion），在ZenFS和ZWAL中都将其视为释放存储资源的操作，与其他数据删除并无不同。由于ZWAL有专用的区域集合，因此可以随时安全地重置（标记为删除的特定区域），而不会影响其他数据。删除可以是主动的（即立即执行）或者是延迟的（即在需要释放存储资源时执行）。

### ZWAL 的实现

ZWALs使用io_uring和NVMe直通来发起区域追加操作，因为Linux块层不支持区域追加。为了将数据与WAL区域分离开，作者在ZenFS的元数据和数据区域之间预留了一组专用的区域，用于存储WAL。在示意图中，用“W”表示WAL，用“M”表示元数据，用“D”表示数据。WAL区域的数量可以在格式化时进行配置。

另外，为了支持ZWALs在RocksDB中的使用，作者修改了一个函数。在删除WAL时，RocksDB首先将WAL移动到归档目录，并在稍后的时间点才物理删除它们。但由于WAL使用的区域数量有限，这可能会导致空间不足的错误，因此作者强制RocksDB立即删除旧的WAL。

需要注意的是，虽然RocksDB提供了各种WAL过滤器，但作者并不指望这些过滤器在ZWALs上有不同的功能。因此，可以将现有的WAL过滤器直接应用于ZWALs。



## ZWAL评估

在本节中，我们评估了在 RocksDB + ZenFS 中实现的 ZWAL 的性能。

吞吐量；恢复时间；YCSB；屏障设置对吞吐量和恢复时间的影响。（使用的障碍大小默认等于 SSD 的Zone大小。）

配置：

![image-20240513004832281](ZNS.assets/image-20240513004832281.png)

### WAL写入性能

ZenFS和ZWALs都为WAL缓冲写请求，因为这可能会显著提高吞吐量（代价是更低的持久性）。由于其性能潜力，我们还调查了缓冲区大小对吞吐量的影响，使从业者可以在吞吐量和持久性之间进行权衡。



一：我们使用RocksDB的db_bench [14]基准测试以及fillrandom工作负载评估两种WALs，使用了5 GiB的4 KiB KV对。我们配置ZWALs以最大QD为32进行区域追加（最佳值；请参阅图2b）

![image-20240513005029520](ZNS.assets/image-20240513005029520.png)。



二：

图4显示了随着缓冲区大小增加（x轴）的吞吐量（y轴）。缓冲区大小越大，WAL合并到一个I/O请求中的PUT请求越多（例如，使用16 KiB缓冲区和4 KiB请求，每4个请求被合并一次）。ZWALs在所有评估的缓冲区大小上都优于ZenFS的WALs，从256 KiB缓冲区的1.92倍吞吐量增加到4 KiB缓冲区的13.94倍。ZenFS的WALs的峰值吞吐量（未显示）是使用1 MiB缓冲区时的48.71 KIOPS。我们没有显示大于256 KiB缓冲区大小的结果，因为在ZWALs中存在实现错误。根据这些结果，我们得出结论，ZWALs显着提高了在具有高区域内并行性的ZNS SSD上的LSM-tree写入吞吐量。

![image-20240513005112720](ZNS.assets/image-20240513005112720.png)

虽然在图中没有显示，但是ZWALs对于大于区域追加大小限制（ZASL）的I/O请求不会扩展。ZASL定义了区域追加的最大请求大小；因此，如果请求大于ZASL，则需要将其拆分为多个子请求。如果请求被拆分，并且每个片段都被单独发送，则SSD可以对它们进行重新排序。当前的ZWAL实现不支持无序片段，并且回退到一次发送一个请求的方式，逐个发送所有请求片段，显著降低了性能。我们可以通过支持无序片段来解决这个挑战（未经评估），例如，为每个片段分配自己的序列号。

![image-20240513005651381](ZNS.assets/image-20240513005651381.png)



三:![image-20240513005639922](ZNS.assets/image-20240513005639922.png)


应用工作负载YCSB

我们使用当今最先进的Yahoo云服务基准（YCSB）[9]工作负载A（50%读取，50%更新），B（95%读取，5%更新），D（95%读取，5%插入）和E（95%扫描，5%插入）评估ZWALs的应用性能。选择这些工作负载是因为它们使用PUT，即写入WAL。请注意，更新操作包括顺序读取和写入。在每个负载阶段之前，我们重置所有ZNS区域并重新格式化文件系统。所有工作负载具有相同的负载阶段；使用商用可用SSD填充25 GiB的KV对，使用模拟SSD填充20 GiB。在运行阶段，我们为每个工作负载发出100万个操作。我们将RocksDB的写缓冲区大小和目标文件大小设置为区域大小，将KV对大小设置为4 KiB和1 KiB（默认YCSB大小）分别用于模拟和商用可用设备。WAL缓冲区大小为8 KiB，并且我们以最大QD 32进行区域追加（参见图6）。

图6a显示了模拟SSD的YCSB吞吐量。最大的吞吐量增长发生在负载阶段（8.56倍）—与图2b相匹配—因为它仅向WAL发出PUT请求。运行阶段也显示了显著的性能增长，但程度较小（例如，对于工作负载D，最高达2.96倍），因为这些工作负载包括读取，并且读取和写入请求竞争相同的SSD资源。重复实验（未显示）使用较大的缓冲区大小显示ZWALs的吞吐量几乎没有好处，类似于我们在§2中观察到的情况。

图6b显示了商用可用SSD的吞吐量。与模拟设备类似，对于PUT-heavy的工作负载，例如负载阶段（27.39%）和工作负载D（33.02%），存在显著的吞吐量提高，并且对于更新或扫描-heavy的工作负载，则较少，例如A（12.51%）和E（6.26%）。对于这个设备，吞吐量的差异较小，因为区域追加可以扩展到QD 4（见图2a）。与先前的实验类似，使用较大的缓冲区进行重复实验显示出写入I/O和区域追加之间没有显著的性能差异。

总之，对于PUT-heavy的工作负载，ZWALs在商用可用的ZNS SSD上导致了显着的吞吐量提高（最高达33.02%）。然而，对于包含写入和读取混合的工作负载（例如扫描-heavy的工作负载），吞吐量的提高较少（6.26%）。

## 结论

分区命名空间（ZNS）SSD可实现LSM树的稳定吞吐量，但已知在LSM树的WAL中会导致写入吞吐量挑战。在这项工作中，我们利用了ZNS特定的区域追加操作来解决这一挑战，并展示了我们的方法显著提高了写入吞吐量。我们相信本工作的贡献展示了区域追加在LSM树之外的潜力，因为我们的序列号过程通常适用于各种情况，鼓励在应用程序和数据结构中进一步利用区域追加。为了促进进一步的研究，我们在https://github.com/stonetresearch/zwal 上发布了本研究的工件。





# WA-Zone

> 研究了基于LSM树的数据管理优化方法以提高ZNS SSDs的使用寿命。

这篇文章介绍了一种称为WA-Zone的技术，旨在有效平衡ZNS SSD中的区域磨损，特别考虑了LSM树的访问模式。ZNS SSD将存储空间分成顺序写区域，以降低DRAM利用率、垃圾收集和过度配置的成本。然而，LSM树的当前压缩机制导致数据的访问频率（即热度）变化很大，从而在区域之间产生极端不平衡的擦除计数分布。这种不平衡显著限制了SSD的寿命。此外，当前的区域重置方法涉及对未使用块的大量不必要的擦除操作，进一步缩短了SSD的寿命。

WA-Zone技术首先提出了一个具有磨损感知的区域分配器，动态地将不同热度的数据分配到具有相应寿命的区域，实现擦除计数在区域之间的均匀分布。然后，提出了一种基于部分擦除的区域重置方法，以避免不必要的擦除操作。此外，由于新颖的区域重置方法可能导致区域中块的擦除计数分布不平衡，因此提出了一个具有磨损感知的块分配器。基于FEMU模拟器的实验结果表明，与基线方案相比，WA-Zone技术提高了ZNS SSD的寿命5.23倍。

## 引言

介绍了ZNS SSDs的特点及其在LSM树数据库中的应用，并指出现有的LSM树压缩机制会导致不同区段之间的磨损不均，缩短SSD的寿命。此外，现有的区段重置方法也会产生大量不必要的擦除操作，进一步缩短了SSD的寿命。

现有工作：

- 设计了一种基于段的GC方案，将冷段分配到一个区域，将冷段与其他段隔离开【9】。
- 提出了一种高效的键值数据放置方法，将同一层的数据分配到一个区域，因为这些数据具有相似的生命周期【34】。
- 由于具有重叠键范围的数据（即LSM树中的SSTable）可能会被合并，Lee等人【24】建议将具有重叠键范围的数据放置在同一区域。此外，为了更好地配合当前的LSM树压缩机制，Jung等人【22】进一步区分同一层中的长期数据和短期数据，以确保每个区域中的数据具有相似的生命周期。

（问题）现有的ZNS SSD数据分配策略通过将生命周期相似的数据分配到同一分区来减少写放大效应，但忽略了分区间磨损均衡的问题。由于LSM树中的数据具有不同的生命周期，这导致各分区的磨损不均衡，极大地缩短了ZNS SSD的寿命。此外，当前的分区重置机制在分区内数据全部失效时Reset，即使分区内有大部分未使用的块也会被擦除，进一步减少了SSD的寿命。

（解决方案）WA-Zone提出了一种新颖的分区管理技术，包含分区间管理和分区内管理两个方面：

1. **分区间管理**：
   - **面向磨损的分区分配器**：动态分配LSM树低层级中最热的数据到磨损最小的分区，以实现分区间的磨损均衡。
2. **分区内管理**：
   - **基于部分擦除的分区重置方法**：减少分区重置时对未使用块的不必要擦除操作。
   - **面向磨损的块分配器**：在一个分区内均匀分配擦除次数。

#### 实现与评估

WA-Zone技术被实现并集成到文件系统和设备中，并通过一个改进的模拟器进行了深入的实验评估，验证了其在典型工作负载下的有效性。

#### 主要贡献

- 提出了一个考虑LSM树访问模式的面向磨损的分区分配器，有效均衡分区间的擦除次数，提高ZNS SSD的寿命。
- 提出了基于部分擦除的分区重置方法，避免了对未使用块的不必要擦除操作。
- 实现了一个面向磨损的块分配器，在分区内实现磨损均衡。
- 通过深入的实验评估，展示了WA-Zone在提升ZNS SSD寿命方面的有效性。

**动机**：分析了现有的区域分配和重置方法，展示了现有方法导致的擦除计数分布不均和不必要的擦除操作问题，从而提出了新的区域管理方法的动机。



## 背景

介绍LSM-Tree，ZNS SSD的背景。分析LSM on ZNS的数据的生命周期问题。

### LSM-Tree（可跳过）

![image-20240617154855339](ZNS.assets/image-20240617154855339.png)

LSM树（Log-Structured Merge Tree）是一种高性能、写效率的数据结构。与其他数据结构（如B+树）相比，LSM树在写密集型工作负载中表现更佳，得益于将随机写操作转换为顺序写操作。

目前，LSM树的主要数据压缩策略分为两种：尺寸分层压缩（size-tiered compaction）和层级压缩（leveled compaction）。层级压缩相比尺寸分层压缩，具有更高的读性能和更低的空间需求，因此被广泛应用于现代读写密集型数据库中。

**LSM树的写操作过程**

1. **写入WAL和Memtable**：当一个键值对到达时，首先写入WAL（预写日志，用于数据恢复）和Memtable（存储在内存中的缓冲区，提供写、读和删除接口）。
2. **Memtable排序和转换**：当Memtable的大小达到预设阈值时，会转换为只读的Immutable Memtable。
3. **生成SSTable**：多个Immutable Memtables合并为一个SSTable（排序字符串表），并刷新到磁盘或SSD存储中。SSTables组织成多个有限大小的层级，新的SSTable首先写入第0层。
4. **层级压缩**：如果第0层的大小超过预设大小，会选择一个SSTable并与第1层中有重叠键范围的SSTables合并，形成新的第1层SSTables。如果第1层的大小仍超过预设大小，则重复压缩过程直到最后一层。层级压缩确保同一层级的键值数据是唯一且有序的，从而减少传统键值存储的读放大和空间放大。

**不平衡的写分布**

由于逐层压缩机制，第0层、第1层和第2层的SSTables有更多的机会被压缩，这导致这些较低层级的SSTables频繁更新，其寿命通常短于较高层级的SSTables。大多数写入和更新集中在低层级的SSTables，导致极不平衡的写分布，这会显著缩短SSD的有限寿命。

### ZNS SSD架构（可跳过）

随着SSD的容量和密度增加，传统的块接口SSD面临诸多挑战，例如大量的DRAM成本用于页面映射表、写放大问题以及由设备内部垃圾回收引起的过度预留空间 [27, 29, 38]。来自ZAC/ZBC标准（用于柱状磁记录硬盘驱动器）[8, 45, 47] 和开放通道SSD [2, 44] 的进化——Zoned Namespace (ZNS)为这些挑战提供了有效的解决方案。与此同时，ZNS命令集已经标准化在NVMe 2.0规范中 [43]，并且作为下一代接口已经得到广泛研究。目前，包括三星、SK Hynix和西部数据在内的许多SSD制造商已经推出了他们的新一代企业级ZNS SSD产品。

![image-20240617160451118](ZNS.assets/image-20240617160451118.png)

Figure 2展示了ZNS SSD的典型架构。多个位于不同闪存芯片上的块首先被分组成一个区域 。这种方式下，ZNS SSD的逻辑地址空间被划分为固定大小的（例如512MB）区域，这些区域可以随机读取但必须顺序写入。

与块接口SSD相比，ZNS SSD展现出许多显著的优势。首先，减少了设备中映射表的DRAM成本。设备中只预先配置了区域与块之间的粗粒度映射表。其次，避免了设备内部的垃圾回收和过度预留空间。主机直接负责在区域上的数据分配和垃圾回收，简化了SSD的*闪存翻译层（FTL）*功能。支持区域管理的文件系统，如F2FS [16]、ZenFS [17]和Btrfs [48]，已经增加了相关模块以支持区域管理。

第三，减少写放大效应。由于避免了设备内部的垃圾回收，因此可以直接消除设备端的写放大效应。此外，主机可以利用应用程序的访问模式，在区域上执行有效的数据分配，通过数据迁移进一步减少写放大效应。因此，根据应用程序的访问模式，提出了许多数据放置技术来在ZNS SSD上最小化写放大效应。

### ZNS中的映射机制

ZNS SSD的映射机制在NVMe ZNS规范中未明确规定，驱动厂商可以选择不同的映射方案，主要分为静态映射和动态映射。

**静态映射**：一个区固定映射到多个擦除块，减少了映射表的空间和时间开销，内部结构对主机更透明，便于与应用的访问特性协同优化，性能更可预测。

**动态映射**：在区打开时动态映射特定块，灵活性更高，适应不同应用的扩展性更好，但会增加空间和时间开销，优化变得复杂。

本文重点讨论静态映射ZNS SSD的磨损均衡优化，以充分利用LSM树数据库的数据访问模式。



#### ZNS中的磨损均衡

磨损均衡通常用于延长基于闪存的SSD的使用寿命，实现在FTL中。

1. **传统SSD中的设备端磨损均衡**：
   
   - 传统SSD在设备端实现磨损均衡，因其在SSD的DRAM中维护L2P（逻辑到物理）映射表，主机无法直接访问内部资源信息。
   - 设备端磨损均衡通常利用时间局部性原理识别热数据，将擦除次数最少的块分配给热数据 
2. **新兴SSD中的主机端磨损均衡**：
   
   - 开放通道SSD和ZNS SSD等新兴SSD将大部分FTL功能实现于主机端。
   - 主机能够更有效地感知应用程序的访问模式，从而进行协同优化，提高SSD的性能（如磨损均衡） 。
3. **ZNS SSD的磨损均衡**：
   
   现有的磨损均衡策略，例如：
   - **轮询方式**：将空闲块映射到新区域
   - **最小擦除计数优先**：在打开新区域时，优先映射擦除次数最少的块
   
   持有冷数据的打开的块不能被优先回收，导致擦除次数在分区间分布不均。因此，本文提出了一种新的面向磨损的分区分配器，以改进ZNS SSD的寿命。

#### 现有分区重置机制

ZNS SSD将分区回收的责任转移到主机，通常在文件系统中实现，如ZenFS中的分区清理和F2FS中的段清理。通常，当可用空间低于指定阈值时，触发区回收，首先选择一个有效数据较少的受害区，然后将该区的所有有效数据迁移到其他区，最后重置受害区以释放空间。然而，这会导致大量数据迁移开销，引发性能下降和I/O阻塞等问题。

ZenFS实现了一种先进的运行时区重置方案。其核心思想是在区内所有数据都变为无效时就重置该区。该方案能有效减少区回收的频率。然而，即使一个区有很多未使用的空间，只要该区内的所有数据变为无效，该区就会被重置。

此外，区重置命令会擦除该区内的所有块，包括未使用的块。这些不必要的擦除操作进一步缩短了SSD的寿命。为了解决这个问题，本文提出了一种基于部分擦除的区重置方法，以减少在未使用块上的不必要擦除操作。



## 3.动机（访问模式）

在本节中，我们首先基于RocksDB的典型工作负载分析ZNS SSDs中擦除计数在各区之间的分布（详细的实验配置参见第5节）。然后，我们讨论未使用块上的不必要擦除操作。最后，基于这些分析，给出本文的研究动机。

3.1 区间间擦除计数的不均衡分布

![image-20240626034419571](ZNS.assets/image-20240626034419571.png)

图3显示了写入1000万和2000万个键值对后擦除计数在各区间的分布。显然，大部分擦除计数集中在少数几个区内。

3.2 未使用块上的不必要擦除操作

![image-20240626034534518](ZNS.assets/image-20240626034534518.png)

图4(b)展示了在各种工作负载下重置4000个区域时的空间利用率。所有区域的平均空间利用率为70%。特别是，32.35%的区域空间利用率低于30%。当这些区域被重置时，其中超过70%的块未被使用。此外，37.60%的区域空间利用率低于50%。考虑到持有大量未使用块的区域比例很大，应提出一种更复杂的区域重置方法，以减少不必要的擦除操作，从而延长SSD的寿命。

## WA-ZONE: LSM树在ZNS SSD上的磨损感知区管理优化

如图5，根据LSM树应用的访问模式，WA-Zone首先动态地将不同热度的数据分配到对应生命周期的区，以实现跨区的磨损均衡。此外，WA-Zone采用了一种新的区重置方法，消除不必要擦除操作。为了充分利用这种新方法，还设计了一种新的块分配策略，使区内块的擦除计数均匀分布。

![image-20240626035718203](ZNS.assets/image-20240626035718203.png)

- 热度分类。
- 区域分配。根据数据热度，设备磨损来分配区域（将最热的数据分配到磨损最小的区，并将最冷的数据写入磨损最大的区，以实现**区间磨损均衡**）
- 基于部分擦除的区重置。集成到SSD控制器的区域内管理部分，以避免在区回收时对未使用块的不必要擦除操作。
- 实现磨损感知的块分配模块，使区域内所有块的擦除计数均匀分布。

实现上，首先将数据热度分类模块集成到文件系统（如ZenFS）的跨区管理部分，用于分类LSM树应用（如RocksDB和LevelDB）的数据热度。其次，根据数据热度实现磨损感知的区分配模块，以平衡区间的磨损。该模块第三，将基于部分擦除的区重置模块集成到SSD控制器的区内管理部分，以避免在区回收时对未使用块的不必要擦除操作。最后，实现磨损感知的块分配模块，使区内所有块的擦除计数均匀分布。

本节的剩余部分将详细介绍上述WA-Zone模块，这些模块分为跨区管理和区内管理两部分。





### 区间管理

//区分配 和 冷数据迁移

本节介绍了数据热度分类和磨损感知区分配模块。这些模块旨在实现跨区的磨损均衡。

#### 4.1.1 数据热度分类

由于逐层压缩机制，同一层级的数据有相同的压缩机会。此外，较低层级的数据有更多的压缩机会。通常，同一层级的数据具有相似的生命周期，而较低层级的数据相较于较高层级的数据生命周期更短。

因此，我们可以根据LSM树中数据的层级有效地分类数据的生命周期。许多相关研究集中于将  同一层级的数据分配到一个区域以减少写放大。相反，本文重点在于动态地将不同热度的数据分配到相应的区域，以平衡跨区的磨损。为此，我们进行了一系列实验来分析不同层级数据的生命周期差异（详细实验配置参见第5节），如图6(a)所示。实验结果显示了两个有趣的发现：

![image-20240626160350765](ZNS.assets/image-20240626160350765.png)

1. **Level 0和Level 1的数据具有相似的生命周期**：当内存缓冲区满时，ImmuTable会合并成一个SSTable，并存储在Level 0。Level 0包含了最新写入的数据。只有当Level 0的大小达到预设阈值时，数据才会写入下一层级。因此，Level 0存储的是LSM树中生命周期最短的数据。由于Level 0的数据来自不可变内存表（ImmuTable），且未按键排序，大部分Level 1的数据会频繁地与Level 0的数据进行压缩。因此，Level 0和Level 1的数据具有相似的生命周期。
2. **较高层级的数据生命周期较长**：相比之下，较高层级（如Level 2及以上）的数据在压缩过程中更少参与，因此这些数据的生命周期更长。例如，Level 2数据的平均生命周期是Level 1数据的6倍，而Level 3数据的平均生命周期是Level 1数据的10倍。

（还是0，1层一组，其他层一组）

#### 4.1.2 磨损感知区分配器

核心思想是根据磨损（即擦除计数）对区进行排序，并将区分类成与数据热度等级数相等的组。使数据热度等于区的磨损等级，即让热数据可以存储在磨损较小的区。

然而，由于冷数据可能始终保持不变，最初包含冷数据的高磨损区将变成低磨损区(?)，导致擦除计数在区间间分布不均衡。为了进一步平衡跨区的磨损，提出了一种冷数据迁移算法，将冷数据从低磨损区迁移到高磨损区。因此，我们提出了区分组方法、空闲区分配器和冷数据迁移算法，具体如下：

1. **按磨损对区进行分组**：如图7(b)所示，首先获取ZNS SSD中区的最大擦除计数（ECmax）和最小擦除计数（ECmin）。然后，将EC_max和EC_min之间的范围分成n段，每段长度为R。n是数据热度等级数，R的计算公式：$ R = \frac{ECmax - ECmin}{n} $

2. **空闲区分配器（FZA）**：当新数据需要新的区时，FZA动态地将数据分配到热度等级接近的数据区，从而平衡跨区的磨损。算法1给出了FZA的四个主要步骤，将热度为h的数据写入新区。

   - **步骤1**：在h级空闲区列表中搜索可用区。如果h级空闲区列表中有空闲区，则将列表中磨损最小的区分配给数据。此外，数据的热度更新到区的生命周期值字段。如果h级空闲区列表中没有空闲区，FZA将寻找与h级区磨损范围相似的区。
   
   - **步骤2**：从(h-1)级到1级的空闲区列表中寻找最大磨损区（Z_{mi,mj}），并计算该区的磨损与h级磨损范围之间的差异（DM）。
   
   - **步骤3**：从(h+1)级到n级的空闲区列表中寻找最小磨损区（Z_{si,sj}），计算差异（DS）。
   
   - **步骤4**：根据DM和DS的大小，在Zsi,sj和Zmi,mj之间进行选择。如果DM小于等于DS，则将数据分配到Zmi,mj区；否则，将数据分配到Zsi,sj区。
   
     每个区组维护两个列表：空闲区列表和已用区列表。根据擦除计数，将区分配到n个组中。
   
   理想情况下，数据应该分配到与其热度等级相同的区，即热度为i的数据应写入i级区。通过这些步骤和算法，磨损感知区分配器可以有效地实现**区域间的磨损均衡**，从而延长ZNS SSD的使用寿命。![image-20240626163952929](ZNS.assets/image-20240626163952929.png)
   
   >上文的DS和DM就是与各自侧的擦除次数上下界的差值
   >
   >- **DM (Difference in Wear of Maximum Zone)**：这是指从(h-1)级到1级的空闲区列表中找到的最大磨损区（Zmi,mj）的磨损与h级磨损范围之间的差异。具体计算方式如下：
   >
   >  $DM = \left| \text{Wear}(Zmi,mj) - \left(ECmin + (h - 1) \times R\right) \right|$
   >
   >  其中，\(\text{Wear}(Zmi,mj)\)表示最大磨损区（Zmi,mj）的磨损计数，\(ECmin\)是最小擦除计数，\(h\)是当前数据的热度级别，\(R\)是磨损范围段的长度。
   >
   >- **DS (Difference in Wear of Minimum Zone)**：这是指从(h+1)级到n级的空闲区列表中找到的最小磨损区（Zsi,sj）的磨损与h级磨损范围之间的差异。具体计算方式如下：
   >
   >  $DS = \left| \text{Wear}(Zsi,sj) - \left(ECmin + h \times R\right) \right|$
   >
   >  其中，$\text{Wear}(Zsi,sj))$表示最小磨损区（Zsi,sj）的磨损计数，\(ECmin\)是最小擦除计数，\(h\)是当前数据的热度级别，\(R\)是磨损范围段的长度。
   
3. FAZ能自适应平衡ZNS SSDs中的磨损，但在实际负载下，冷数据无法及时回收会导致磨损不平衡。因此，我们提出了冷数据迁移（CDM）方案来促进磨损均衡。

   触发条件: 当冷数据写入磨损较小的区，并且该区可能不会及时回收时，触发CDM。

   通过这种方法，确保冷数据不在磨损较小的区中长期驻留，从而实现更好的磨损均衡。

   



## 区内管理

// Zone Reset和 Block Alloc

区内管理旨在实现区内块之间的磨损均衡。该部分包括基于部分擦除的区重置模块和磨损感知块分配器模块，以消除未使用块上的不必要擦除操作并均匀分配擦除计数。

#### 4.2.1 基于部分擦除的区重置

当前的区重置方法在重置区时会擦除未使用的块。正如3.2节所讨论的，所有区的平均空间利用率约为70%，这意味着近30%的擦除操作是在未使用的块上进行的。理论上，如果我们能消除这些不必要的擦除操作，可以延长SSD寿命约30%（？）。因此，提出了基于部分擦除的区重置方法以实现这一目标。

![image-20240626170352755](ZNS.assets/image-20240626170352755.png)

如图8(a)。ZNS SSD将逻辑块地址（LBA）划分为多个区。每个区有一段连续的LBA，并映射到多个物理块。同时，一个写指针记录当前在LBA中的写入位置。

首先用写指针计算已写入块的LBA范围。其次，根据已写入的LBA范围，可以在区映射表中追踪已使用的物理块。第三，实施部分擦除功能以擦除这些已使用的块。

虽然这种新颖的区重置方法可以消除不必要的擦除操作，但可能会导致擦除计数在块间的极度不均衡。具体来说，当一个区被重置时，其写指针将移动到区LBA的起始位置。当该区重新分配时，新数据将从LBA的起始位置写入。因此，大多数擦除计数将集中在小LBA的块上。为了解决擦除计数分布极度不均衡的问题，进一步提出了磨损感知块分配器。否则，存储系统不能充分利用基于部分擦除的区重置方法。

#### 4.2.2 磨损感知块分配器

为了均衡区内的磨损，磨损感知块分配器会在分配新数据时，将数据均匀地写入到各个块中，而不是集中在某些特定块上。这样可以避免擦除计数在少数块上过度集中，从而延长SSD的整体寿命。

![image-20240626172600234](ZNS.assets/image-20240626172600234.png)

图8(b)展示了磨损感知块分配器的主要机制。基本思想是从最近一次重置时的某个物理块地址（PBA）开始写入新区。对于新获取的区的写请求，我们必须将区LBA的起始位置与区内最近写入块的PBA关联起来。为实现这一功能，我们将区视为一个循环队列，即采用模运算来关联物理地址和逻辑地址，避免任何超过区容量的无效地址。

磨损感知块分配器主要包括以下四个步骤：

1. **记录偏移指针**：当一个区被重置时，偏移指针记录PBA的偏移，即起始PBA与最近写入PBA之间的距离（PBAop）。

2. **计算新数据的PBA**：当新数据需要写入区时，新数据的PBA可以通过以下公式计算：

   $PBAw=LBAstart+(LBAwp+PBAop)mod  ZC$

   其中，LBAstart和ZC分别表示起始LBA和区容量，LBAwp是写指针与起始LBA之间的距离。

3. **读取数据的PBA**：当需要读取区内的数据时，数据的PBA可以通过以下公式计算：

   $PBAr=LBAstart+(LBAr+PBAop)mod  ZC$

   其中，LBAr表示数据的LBA。

4. **更新偏移指针**：当调用重置命令时，更新偏移指针，其计算公式如下：

   $PBAop'=(LBAwp−LBAstart+PBAop)modZC$

总之，磨损感知块分配器利用偏移指针来维护上次重置时当前写入的PBA。对于每个数据请求，我们通过简单的模运算重新计算新的PBA。这种方法的存储和性能开销可以忽略不计，对ZNS SSDs的整体性能没有影响。



简单来说，在区域内：

1. **部分擦除**：在重置一个区时，只重置该区内已经使用过的块，而不是全部块。
2. **起始块**：当该区被重新分配时，从上次重置的末尾块开始作为新的起始块写入数据。

这样可以避免不必要的擦除操作，并均衡区内块的磨损。

## 实验

基于FEMU，small-zone ZNS SSD

![image-20240626174846566](ZNS.assets/image-20240626174846566.png)

**区间管理**：在ZenFS中实现数据热度分类和磨损感知区分配器（FAZ），以及冷数据迁移模块（CDM）。

**区内管理**：在ZoneFTL中实现基于部分擦除的区重置和磨损感知块分配器，通过地址重定位模块实现块的均匀磨损分配。

最后，使用RocksDB的内置基准测试工具（db_bench）生成不同工作负载，以评估WA-Zone的有效性。使用包含2000万个键值对和不同访问特征的六个工作负载，包括fillrandom（称为Random）、fillrandom+overwrite（称为Random+OW）、fillrandom+updaterandom（称为Random+U）、fillseq（称为Seq）、fillseq+overwrite（称为Seq+OW）和fillseq+updaterandom（称为Seq+U）。此外，还选择了三个具有偏斜访问分布的YCSB工作负载（即YCSB-A、YCSB-B和YCSB-F）来评估所提出技术的有效性。



### 5.2 实验结果与分析

**区间管理**：

- **对比方案**：Origin-Zone（基线ZenFS）、Seq-Zone（顺序分配）、eZNS（优先分配最少擦除次数）和Inter-Zone。

- **结果**：Inter-Zone实现了更均衡的磨损分布，减少了最大和最小擦除计数之间的差距和标准差。记Origin-Zone标准差为1，Seq-Zone=72.31%  eZNS=78.66% Inter-Zone=90.16%

  ![image-20240626180538834](ZNS.assets/image-20240626180538834.png)

**区内管理**：

- **对比方案**：PE-Zone（仅部分擦除重置）和Intra-Zone（部分擦除重置+磨损感知块分配器）。

- **结果**：PE-Zone减少了不必要的擦除操作，Intra-Zone进一步平衡了块间的磨损，显著降低了块擦除计数的标准差。

  ![image-20240626180943993](ZNS.assets/image-20240626180943993.png)

图10显示了PE-Zone和Origin-Zone处理九个不同工作负载时的总块擦除计数。与Origin-Zone相比，PE-Zone可以分别减少41.99%、45.67%、31.86%、67.47%、55.94%、36.21%、27.56%、29.54%和31.24%的总块擦除计数。平均而言，可以避免40.83%的总块擦除计数。这有助于将ZNSSSD的写入流量减少40.83%(?)，并将其寿命上限提高40.83%，为进一步改进提供了空间。

![image-20240626181236349](ZNS.assets/image-20240626181236349.png)

图11显示了PE-Zone和Intra-Zone处理中每个区域的块擦除计数标准差。PE-Zone显著减少了ZNS SSD的写入流量。然而，每次重新分配区域时，该区域总是从第一个块开始写入，导致块间擦除计数分布不均，缩短了ZNS SSD的寿命。因此，我们提出了Intra-Zone中的磨损感知块分配器，以平衡区内块之间的擦除计数。我们计算了每个区域的块擦除计数标准差来评估所提出的方案。PE-Zone获得的最大标准差为11.42，平均标准差为4.91。与PE-Zone相比，Intra-Zone平衡了区内块之间的磨损。此外，Intra-Zone获得的最大和平均标准差仅为0.51和0.38。因此，Intra-Zone将区内擦除操作均匀分配到所有块上。





**综合比较**：

- **对比方案**：Origin-Zone、Inter-Zone、Inter-Zone+PE-Zone、Inter-Zone+Intra-Zone、eZNS、Seq-Zone和Ideal。

- **结果**：Inter-Zone+Intra-Zone接近Ideal方案，在块间最大擦除计数和首次失效时间方面表现出色，显著提升了ZNS SSD的寿命。

  ![image-20240626182157690](ZNS.assets/image-20240626182157690.png)

图12展示了九个不同工作负载中各块的最大擦除计数

与Origin-Zone相比，Inter-Zone减少了69.37%的块间最大擦除计数。Ideal中的块间最大擦除计数约为Inter-Zone+Intra-Zone的87.82%。

![image-20240626182441190](ZNS.assets/image-20240626182441190.png)

图13展示了九个不同工作负载中ZNS SSD块的首次失效时间。

假设每个块的最大擦除次数（ME）相同，如果擦除次数超过ME，块将失效。

与Origin-Zone相比，Inter-Zone在九个工作负载中分别实现了3倍、2.79倍、3.35倍、7.07倍、4.54倍、4.37倍、2.67倍、1.73倍和2.4倍的首次失效时间。

结合磨损感知块分配器，Inter-Zone+PE-Zone进一步将九个工作负载的首次失效时间平均提高了40.44%。



### WA-Zone的开销总结

#### 空间开销

- **数据热度分类模块**：需要维护h级自由区列表和h级已用区列表，每个区的擦除计数和区编号各占4字节，总计8字节。支持232个区的空间开销不到8KB，这在主机内存中是可以接受的。
- **元数据（PBAop）**：记录起始PBA和最近写入PBA之间的距离，4字节大小足以记录4GB区的偏移量，总空间开销小于8KB，存储在每个区的预留空间中，以避免DRAM空间消耗。

#### 时间开销

- 主机端
  - **数据热度分类**：插入算法时间复杂度为O(n)。
  - **磨损感知区分配器**：FZA时间复杂度为O(n)，CDM时间复杂度为O(n^2)。
  - 这些算法运行在主机的通用处理器上，时间开销可以忽略不计。
- SSD端
  - **地址计算**：每次访问数据时，计算PBA的时间复杂度为O(1)，地址重定位过程在纳秒级时间内完成。
  - 与SSD的程序延迟（数百到数千微秒）相比，这些时间开销是可以忽略的。

**性能影响**：

- **写入放大**：WA-Zone的写入放大率平均仅增加1.45%。
- **吞吐量和写入延迟**：与Origin-Zone相比，WA-Zone的吞吐量减少1.42%，写入延迟增加2.5%，这些影响在可接受范围内。

总的来说，WA-Zone在空间和时间开销方面都较低，对系统性能影响可以忽略，能够显著提升ZNS SSD的寿命和性能。