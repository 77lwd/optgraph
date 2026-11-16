# -*- coding: utf-8 -*-
"""
Parallel Execution Demo - 验证并发工具调用可行性

场景：查询3个城市的天气（独立任务，可以并发）
"""

import asyncio
import time
from typing import List


# 模拟工具调用
async def call_weather_api(city: str) -> dict:
    """模拟调用天气API（耗时2秒）"""
    print(f"[{time.strftime('%H:%M:%S')}] 开始查询 {city} 的天气...")
    await asyncio.sleep(2)  # 模拟网络延迟
    result = {"city": city, "temp": 25, "weather": "晴天"}
    print(f"[{time.strftime('%H:%M:%S')}] {city} 查询完成: {result}")
    return result


# 串行执行
async def serial_execution(cities: List[str]):
    """串行执行：一个接一个"""
    print("\n=== 串行执行 ===")
    start = time.time()

    results = []
    for city in cities:
        result = await call_weather_api(city)
        results.append(result)

    elapsed = time.time() - start
    print(f"串行总耗时: {elapsed:.2f}秒")
    return results, elapsed


# 并发执行
async def parallel_execution(cities: List[str]):
    """并发执行：同时查询"""
    print("\n=== 并发执行 ===")
    start = time.time()

    # 关键：asyncio.gather() 同时执行多个协程
    tasks = [call_weather_api(city) for city in cities]
    results = await asyncio.gather(*tasks)

    elapsed = time.time() - start
    print(f"并发总耗时: {elapsed:.2f}秒")
    return results, elapsed


async def main():
    """主函数"""
    cities = ["北京", "上海", "深圳"]

    # 测试串行
    serial_results, serial_time = await serial_execution(cities)

    # 等待一下，看得更清楚
    await asyncio.sleep(1)

    # 测试并发
    parallel_results, parallel_time = await parallel_execution(cities)

    # 计算加速比
    speedup = serial_time / parallel_time
    latency_reduction = (1 - parallel_time / serial_time) * 100

    print("\n" + "="*50)
    print("Performance Comparison")
    print("="*50)
    print(f"串行耗时: {serial_time:.2f}秒")
    print(f"并发耗时: {parallel_time:.2f}秒")
    print(f"加速比: {speedup:.2f}x")
    print(f"Latency降低: {latency_reduction:.1f}%")
    print("="*50)


if __name__ == "__main__":
    # 运行异步主函数
    asyncio.run(main())
