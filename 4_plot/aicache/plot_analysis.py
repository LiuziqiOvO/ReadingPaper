import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
from pathlib import Path

# 设置绘图风格和中文字体
plt.style.use('seaborn')
plt.rcParams['font.sans-serif'] = ['SimHei']  
plt.rcParams['axes.unicode_minus'] = False  
plt.rcParams['figure.facecolor'] = 'white'
plt.rcParams['axes.facecolor'] = 'white'
plt.rcParams['savefig.dpi'] = 300
plt.rcParams['figure.autolayout'] = True

# 定义配色方案
COLORS = sns.color_palette("husl", 8)
PLOT_STYLE = {
    'grid.linestyle': '--',
    'grid.alpha': 0.6,
    'grid.color': '#cccccc',
}

# 创建输出目录
PLOT_DIR = Path('plots')
PLOT_DIR.mkdir(exist_ok=True)

def preprocess_data(df):
    """预处理数据，提取位运算配置信息"""
    df['config'] = df['libdas-version'].str.extract(r'>>(\d+)\s+>>(\d+)')
    df['config_str'] = df['config'].apply(lambda x: f'>>{x[0]}>>{x[1]}' if isinstance(x, pd.Series) else None)
    return df[df['config_str'].notna()]

def plot_config_comparison(df):
    """比较不同位运算配置的性能指标"""
    fig, axes = plt.subplots(2, 2, figsize=(20, 16))
    fig.suptitle('不同位运算配置性能对比分析', fontsize=16, y=0.95)
    
    # 计算各配置的平均指标
    metrics = {
        'KIOPS': ('平均IOPS (K)', 'KIOPS'),
        'BW(MiB/s)': ('平均带宽 (MiB/s)', 'BW(MiB/s)'),
        'Hit Ratio(%)': ('缓存命中率 (%)', 'Hit Ratio(%)'),
        'Latency(us)': ('平均延迟 (us)', 'Latency(us)')
    }
    
    for (i, (metric, (title, ylabel))) in enumerate(metrics.items()):
        ax = axes[i//2, i%2]
        sns.boxplot(data=df, x='config_str', y=metric, ax=ax, palette=COLORS)
        ax.set_title(title, pad=20)
        ax.set_xlabel('位运算配置')
        ax.set_ylabel(ylabel)
        ax.tick_params(axis='x', rotation=45)
        
    plt.savefig(PLOT_DIR / 'config_comparison.png', bbox_inches='tight')
    plt.close()

def plot_trace_performance_by_config(df):
    """分析不同trace在各配置下的性能表现"""
    # 过滤出主要的trace文件（非ali-dev-3-part系列）
    main_traces = df[~df['Trace'].str.contains('ali-dev-3-part', na=False)]
    
    fig, ax = plt.subplots(figsize=(15, 8))
    
    configs = main_traces['config_str'].unique()
    x = np.arange(len(main_traces['Trace'].unique()))
    width = 0.8 / len(configs)
    
    for i, config in enumerate(configs):
        data = main_traces[main_traces['config_str'] == config]
        ax.bar(x + i*width, data['KIOPS'], width, 
               label=config, color=COLORS[i], alpha=0.8)
    
    ax.set_ylabel('KIOPS')
    ax.set_title('不同配置下各Trace文件的IOPS表现')
    ax.set_xticks(x + width * (len(configs)-1)/2)
    ax.set_xticklabels(main_traces['Trace'].unique(), rotation=45, ha='right')
    ax.legend(title='配置')
    ax.grid(True, **PLOT_STYLE)
    
    plt.savefig(PLOT_DIR / 'trace_performance_by_config.png', bbox_inches='tight')
    plt.close()

def plot_hit_ratio_analysis(df):
    """分析命中率与性能的关系"""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(20, 8))
    
    # 命中率与延迟的关系
    sns.scatterplot(data=df, x='Hit Ratio(%)', y='Latency(us)', 
                    hue='config_str', style='config_str', ax=ax1)
    ax1.set_title('缓存命中率与延迟的关系')
    ax1.set_xlabel('命中率 (%)')
    ax1.set_ylabel('延迟 (us)')
    
    # 命中率与IOPS的关系
    sns.scatterplot(data=df, x='Hit Ratio(%)', y='KIOPS', 
                    hue='config_str', style='config_str', ax=ax2)
    ax2.set_title('缓存命中率与IOPS的关系')
    ax2.set_xlabel('命中率 (%)')
    ax2.set_ylabel('KIOPS')
    
    for ax in (ax1, ax2):
        ax.grid(True, **PLOT_STYLE)
        ax.legend(title='配置', bbox_to_anchor=(1.05, 1), loc='upper left')
    
    plt.savefig(PLOT_DIR / 'hit_ratio_analysis.png', bbox_inches='tight')
    plt.close()

def plot_ali_trace_analysis(df):
    """分析ali-dev-3-part系列在不同配置下的性能变化"""
    ali_data = df[df['Trace'].str.contains('ali-dev-3-part', na=False)]
    ali_data['Part'] = ali_data['Trace'].str.extract('part-(\d+)').astype(int)
    
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(15, 12))
    
    # IOPS随Part变化
    for config in ali_data['config_str'].unique():
        data = ali_data[ali_data['config_str'] == config].sort_values('Part')
        ax1.plot(data['Part'], data['KIOPS'], 'o-', label=config, alpha=0.8)
    
    ax1.set_title('ali-dev-3-part系列IOPS变化')
    ax1.set_xlabel('Part编号')
    ax1.set_ylabel('KIOPS')
    ax1.grid(True, **PLOT_STYLE)
    ax1.legend(title='配置')
    
    # 带宽随Part变化
    for config in ali_data['config_str'].unique():
        data = ali_data[ali_data['config_str'] == config].sort_values('Part')
        ax2.plot(data['Part'], data['BW(MiB/s)'], 'o-', label=config, alpha=0.8)
    
    ax2.set_title('ali-dev-3-part系列带宽变化')
    ax2.set_xlabel('Part编号')
    ax2.set_ylabel('带宽 (MiB/s)')
    ax2.grid(True, **PLOT_STYLE)
    ax2.legend(title='配置')
    
    plt.savefig(PLOT_DIR / 'ali_trace_analysis.png', bbox_inches='tight')
    plt.close()

def generate_statistics_report(df):
    """生成统计报告"""
    report = []
    
    # 按配置分组计算平均指标
    stats = df.groupby('config_str').agg({
        'KIOPS': ['mean', 'std'],
        'BW(MiB/s)': ['mean', 'std'],
        'Hit Ratio(%)': ['mean', 'std'],
        'Latency(us)': ['mean', 'std']
    }).round(2)
    
    # 保存统计结果
    stats.to_csv(PLOT_DIR / 'performance_statistics.csv')
    
    return stats

if __name__ == "__main__":
    # 读取数据
    df = pd.read_csv('data', delimiter='\t')
    df = preprocess_data(df)
    
    # 生成所有图表
    plot_config_comparison(df)
    plot_trace_performance_by_config(df)
    plot_hit_ratio_analysis(df)
    plot_ali_trace_analysis(df)
    
    # 生成统计报告
    stats = generate_statistics_report(df)
    
    print("分析完成！所有图表和统计报告已保存到plots目录")
    print("\n性能统计概要：")
    print(stats)
    

    
     