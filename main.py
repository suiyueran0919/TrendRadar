# coding=utf-8

import json
import os
import random
import re
import time
import webbrowser
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Union

import pytz
import requests
import yaml


class ConfigManager:
    """配置管理器"""

    @staticmethod
    def _load_config_file() -> Dict:
        """加载配置文件"""
        config_path = os.environ.get("CONFIG_PATH", "config/config.yaml")

        if not Path(config_path).exists():
            raise FileNotFoundError(f"配置文件 {config_path} 不存在")

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config_data = yaml.safe_load(f)

            print(f"配置文件加载成功: {config_path}")
            return config_data

        except Exception as e:
            raise RuntimeError(f"配置文件解析失败: {e}")

    def __init__(self):
        self.config_data = self._load_config_file()
        self.config = self._build_config()
        self.platforms = self.config_data["platforms"]

    def _get_webhook_config(self, config_key: str, env_key: str) -> str:
        """获取 Webhook 配置"""
        env_value = os.environ.get(env_key, "").strip()
        if env_value:
            return env_value

        return (
            self.config_data.get("notification", {})
            .get("webhooks", {})
            .get(config_key, "")
        )

    def _build_config(self) -> Dict:
        """构建配置字典，环境变量优先级高于配置文件"""

        feishu_url = self._get_webhook_config("feishu_url", "FEISHU_WEBHOOK_URL")
        dingtalk_url = self._get_webhook_config("dingtalk_url", "DINGTALK_WEBHOOK_URL")
        wework_url = self._get_webhook_config("wework_url", "WEWORK_WEBHOOK_URL")
        telegram_token = self._get_webhook_config(
            "telegram_bot_token", "TELEGRAM_BOT_TOKEN"
        )
        telegram_chat_id = self._get_webhook_config(
            "telegram_chat_id", "TELEGRAM_CHAT_ID"
        )

        # 输出配置来源信息
        webhook_sources = []
        if feishu_url:
            source = "环境变量" if os.environ.get("FEISHU_WEBHOOK_URL") else "配置文件"
            webhook_sources.append(f"飞书({source})")
        if dingtalk_url:
            source = (
                "环境变量" if os.environ.get("DINGTALK_WEBHOOK_URL") else "配置文件"
            )
            webhook_sources.append(f"钉钉({source})")
        if wework_url:
            source = "环境变量" if os.environ.get("WEWORK_WEBHOOK_URL") else "配置文件"
            webhook_sources.append(f"企业微信({source})")
        if telegram_token and telegram_chat_id:
            token_source = (
                "环境变量" if os.environ.get("TELEGRAM_BOT_TOKEN") else "配置文件"
            )
            chat_source = (
                "环境变量" if os.environ.get("TELEGRAM_CHAT_ID") else "配置文件"
            )
            webhook_sources.append(f"Telegram({token_source}/{chat_source})")

        if webhook_sources:
            print(f"Webhook 配置来源: {', '.join(webhook_sources)}")
        else:
            print("未配置任何 Webhook")

        config = {
            "VERSION": self.config_data["app"]["version"],
            "VERSION_CHECK_URL": self.config_data["app"]["version_check_url"],
            "SHOW_VERSION_UPDATE": self.config_data["app"]["show_version_update"],
            "FEISHU_MESSAGE_SEPARATOR": self.config_data["notification"][
                "feishu_message_separator"
            ],
            "REQUEST_INTERVAL": self.config_data["crawler"]["request_interval"],
            "REPORT_MODE": self.config_data["report"]["mode"],
            "RANK_THRESHOLD": self.config_data["report"]["rank_threshold"],
            "USE_PROXY": self.config_data["crawler"]["use_proxy"],
            "DEFAULT_PROXY": self.config_data["crawler"]["default_proxy"],
            "ENABLE_CRAWLER": self.config_data["crawler"]["enable_crawler"],
            "ENABLE_NOTIFICATION": self.config_data["notification"][
                "enable_notification"
            ],
            "MESSAGE_BATCH_SIZE": self.config_data["notification"][
                "message_batch_size"
            ],
            "BATCH_SEND_INTERVAL": self.config_data["notification"][
                "batch_send_interval"
            ],
            "FEISHU_WEBHOOK_URL": feishu_url,
            "DINGTALK_WEBHOOK_URL": dingtalk_url,
            "WEWORK_WEBHOOK_URL": wework_url,
            "TELEGRAM_BOT_TOKEN": telegram_token,
            "TELEGRAM_CHAT_ID": telegram_chat_id,
            "WEIGHT_CONFIG": {
                "RANK_WEIGHT": self.config_data["weight"]["rank_weight"],
                "FREQUENCY_WEIGHT": self.config_data["weight"]["frequency_weight"],
                "HOTNESS_WEIGHT": self.config_data["weight"]["hotness_weight"],
            },
        }

        return config

    def get_config(self) -> Dict:
        """获取配置字典"""
        return self.config

    def get_platforms(self) -> List:
        """获取平台列表"""
        return self.platforms


print("正在加载配置...")
config_manager = ConfigManager()
CONFIG = config_manager.get_config()
PLATFORMS = config_manager.get_platforms()

print(f"TrendRadar v{CONFIG['VERSION']} 配置加载完成")
print(f"监控平台数量: {len(PLATFORMS)}")


class TimeHelper:
    """时间处理工具"""

    @staticmethod
    def get_beijing_time() -> datetime:
        return datetime.now(pytz.timezone("Asia/Shanghai"))

    @staticmethod
    def format_date_folder() -> str:
        return TimeHelper.get_beijing_time().strftime("%Y年%m月%d日")

    @staticmethod
    def format_time_filename() -> str:
        return TimeHelper.get_beijing_time().strftime("%H时%M分")


class VersionChecker:
    """版本检查工具"""

    @staticmethod
    def parse_version(version_str: str) -> Tuple[int, int, int]:
        """解析版本号字符串为元组"""
        try:
            parts = version_str.strip().split(".")
            if len(parts) != 3:
                raise ValueError("版本号格式不正确")
            return int(parts[0]), int(parts[1]), int(parts[2])
        except (ValueError, AttributeError):
            print(f"无法解析版本号: {version_str}")
            return 0, 0, 0

    @staticmethod
    def compare_versions(current: str, remote: str) -> int:
        """比较版本号"""
        current_tuple = VersionChecker.parse_version(current)
        remote_tuple = VersionChecker.parse_version(remote)

        if current_tuple < remote_tuple:
            return -1  # 需要更新
        elif current_tuple > remote_tuple:
            return 1  # 当前版本更新
        else:
            return 0  # 版本相同

    @staticmethod
    def check_for_updates(
        current_version: str,
        version_url: str,
        proxy_url: Optional[str] = None,
        timeout: int = 10,
    ) -> Tuple[bool, Optional[str]]:
        """检查是否有新版本"""
        try:
            proxies = None
            if proxy_url:
                proxies = {"http": proxy_url, "https": proxy_url}

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/plain, */*",
                "Cache-Control": "no-cache",
            }

            response = requests.get(
                version_url, proxies=proxies, headers=headers, timeout=timeout
            )
            response.raise_for_status()

            remote_version = response.text.strip()
            print(f"当前版本: {current_version}, 远程版本: {remote_version}")

            comparison = VersionChecker.compare_versions(
                current_version, remote_version
            )
            need_update = comparison == -1

            return need_update, remote_version if need_update else None

        except Exception as e:
            print(f"版本检查失败: {e}")
            return False, None


class FileHelper:
    """文件操作工具"""

    @staticmethod
    def ensure_directory_exists(directory: str) -> None:
        Path(directory).mkdir(parents=True, exist_ok=True)

    @staticmethod
    def get_output_path(subfolder: str, filename: str) -> str:
        date_folder = TimeHelper.format_date_folder()
        output_dir = Path("output") / date_folder / subfolder
        FileHelper.ensure_directory_exists(str(output_dir))
        return str(output_dir / filename)


class DataFetcher:
    """数据获取器"""

    def __init__(self, proxy_url: Optional[str] = None):
        self.proxy_url = proxy_url

    def fetch_data(
        self,
        id_info: Union[str, Tuple[str, str]],
        max_retries: int = 2,
        min_retry_wait: int = 3,
        max_retry_wait: int = 5,
    ) -> Tuple[Optional[str], str, str]:
        """获取指定ID数据，支持重试"""
        if isinstance(id_info, tuple):
            id_value, alias = id_info
        else:
            id_value = id_info
            alias = id_value

        url = f"https://newsnow.busiyi.world/api/s?id={id_value}&latest"

        proxies = None
        if self.proxy_url:
            proxies = {"http": self.proxy_url, "https": self.proxy_url}

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Connection": "keep-alive",
            "Cache-Control": "no-cache",
        }

        retries = 0
        while retries <= max_retries:
            try:
                response = requests.get(
                    url, proxies=proxies, headers=headers, timeout=10
                )
                response.raise_for_status()

                data_text = response.text
                data_json = json.loads(data_text)

                status = data_json.get("status", "未知")
                if status not in ["success", "cache"]:
                    raise ValueError(f"响应状态异常: {status}")

                status_info = "最新数据" if status == "success" else "缓存数据"
                print(f"获取 {id_value} 成功（{status_info}）")
                return data_text, id_value, alias

            except Exception as e:
                retries += 1
                if retries <= max_retries:
                    base_wait = random.uniform(min_retry_wait, max_retry_wait)
                    additional_wait = (retries - 1) * random.uniform(1, 2)
                    wait_time = base_wait + additional_wait
                    print(f"请求 {id_value} 失败: {e}. {wait_time:.2f}秒后重试...")
                    time.sleep(wait_time)
                else:
                    print(f"请求 {id_value} 失败: {e}")
                    return None, id_value, alias
        return None, id_value, alias

    def crawl_websites(
        self,
        ids_list: List[Union[str, Tuple[str, str]]],
        request_interval: int = CONFIG["REQUEST_INTERVAL"],
    ) -> Tuple[Dict, Dict, List]:
        """爬取多个网站数据"""
        results = {}
        id_to_name = {}
        failed_ids = []

        for i, id_info in enumerate(ids_list):
            if isinstance(id_info, tuple):
                id_value, name = id_info
            else:
                id_value = id_info
                name = id_value

            id_to_name[id_value] = name
            response, _, _ = self.fetch_data(id_info)

            if response:
                try:
                    data = json.loads(response)
                    results[id_value] = {}
                    for index, item in enumerate(data.get("items", []), 1):
                        title = item["title"]
                        url = item.get("url", "")
                        mobile_url = item.get("mobileUrl", "")

                        if title in results[id_value]:
                            results[id_value][title]["ranks"].append(index)
                        else:
                            results[id_value][title] = {
                                "ranks": [index],
                                "url": url,
                                "mobileUrl": mobile_url,
                            }
                except json.JSONDecodeError:
                    print(f"解析 {id_value} 响应失败")
                    failed_ids.append(id_value)
                except Exception as e:
                    print(f"处理 {id_value} 数据出错: {e}")
                    failed_ids.append(id_value)
            else:
                failed_ids.append(id_value)

            if i < len(ids_list) - 1:
                actual_interval = request_interval + random.randint(-10, 20)
                actual_interval = max(50, actual_interval)
                time.sleep(actual_interval / 1000)

        print(f"成功: {list(results.keys())}, 失败: {failed_ids}")
        return results, id_to_name, failed_ids


class DataProcessor:
    """数据处理器"""

    @staticmethod
    def clean_title(title: str) -> str:
        """清理标题中的特殊字符"""
        if not isinstance(title, str):
            title = str(title)

        cleaned_title = title.replace("\n", " ").replace("\r", " ")

        cleaned_title = re.sub(r"\s+", " ", cleaned_title)

        cleaned_title = cleaned_title.strip()

        return cleaned_title

    @staticmethod
    def is_first_crawl_today() -> bool:
        """检测是否是当天第一次爬取"""
        date_folder = TimeHelper.format_date_folder()
        txt_dir = Path("output") / date_folder / "txt"

        if not txt_dir.exists():
            return True

        files = sorted([f for f in txt_dir.iterdir() if f.suffix == ".txt"])
        return len(files) <= 1  # 0个文件或1个文件都算第一次

    @staticmethod
    def detect_latest_new_titles(
        current_platform_ids: Optional[List[str]] = None,
    ) -> Dict:
        """检测当日最新批次的新增标题，支持按当前监控平台过滤"""
        date_folder = TimeHelper.format_date_folder()
        txt_dir = Path("output") / date_folder / "txt"

        if not txt_dir.exists():
            return {}

        files = sorted([f for f in txt_dir.iterdir() if f.suffix == ".txt"])
        if len(files) < 2:
            return {}

        # 解析最新文件
        latest_file = files[-1]
        latest_titles, _ = DataProcessor._parse_file_titles(latest_file)

        # 如果指定了当前平台列表，过滤最新文件数据
        if current_platform_ids is not None:
            filtered_latest_titles = {}
            for source_id, title_data in latest_titles.items():
                if source_id in current_platform_ids:
                    filtered_latest_titles[source_id] = title_data
            latest_titles = filtered_latest_titles

        # 汇总历史标题（按平台过滤）
        historical_titles = {}
        for file_path in files[:-1]:
            historical_data, _ = DataProcessor._parse_file_titles(file_path)

            # 过滤历史数据
            if current_platform_ids is not None:
                filtered_historical_data = {}
                for source_id, title_data in historical_data.items():
                    if source_id in current_platform_ids:
                        filtered_historical_data[source_id] = title_data
                historical_data = filtered_historical_data

            for source_id, titles_data in historical_data.items():
                if source_id not in historical_titles:
                    historical_titles[source_id] = set()
                for title in titles_data.keys():
                    historical_titles[source_id].add(title)

        # 找出新增标题
        new_titles = {}
        for source_id, latest_source_titles in latest_titles.items():
            historical_set = historical_titles.get(source_id, set())
            source_new_titles = {}

            for title, title_data in latest_source_titles.items():
                if title not in historical_set:
                    source_new_titles[title] = title_data

            if source_new_titles:
                new_titles[source_id] = source_new_titles

        return new_titles

    @staticmethod
    def _parse_file_titles(file_path: Path) -> Tuple[Dict, Dict]:
        """解析单个txt文件的标题数据，返回(titles_by_id, id_to_name)"""
        titles_by_id = {}
        id_to_name = {}

        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            sections = content.split("\n\n")

            for section in sections:
                if not section.strip() or "==== 以下ID请求失败 ====" in section:
                    continue

                lines = section.strip().split("\n")
                if len(lines) < 2:
                    continue

                # id | name 或 id
                header_line = lines[0].strip()
                if " | " in header_line:
                    parts = header_line.split(" | ", 1)
                    source_id = parts[0].strip()
                    name = parts[1].strip()
                    id_to_name[source_id] = name
                else:
                    source_id = header_line
                    id_to_name[source_id] = source_id 

                titles_by_id[source_id] = {}

                for line in lines[1:]:
                    if line.strip():
                        try:
                            title_part = line.strip()
                            rank = None

                            # 提取排名
                            if (
                                ". " in title_part
                                and title_part.split(". ")[0].isdigit()
                            ):
                                rank_str, title_part = title_part.split(". ", 1)
                                rank = int(rank_str)

                            # 提取 MOBILE URL
                            mobile_url = ""
                            if " [MOBILE:" in title_part:
                                title_part, mobile_part = title_part.rsplit(
                                    " [MOBILE:", 1
                                )
                                if mobile_part.endswith("]"):
                                    mobile_url = mobile_part[:-1]

                            # 提取 URL
                            url = ""
                            if " [URL:" in title_part:
                                title_part, url_part = title_part.rsplit(" [URL:", 1)
                                if url_part.endswith("]"):
                                    url = url_part[:-1]

                            title = DataProcessor.clean_title(title_part.strip())
                            ranks = [rank] if rank is not None else [1]

                            titles_by_id[source_id][title] = {
                                "ranks": ranks,
                                "url": url,
                                "mobileUrl": mobile_url,
                            }

                        except Exception as e:
                            print(f"解析标题行出错: {line}, 错误: {e}")

        return titles_by_id, id_to_name

    @staticmethod
    def save_titles_to_file(results: Dict, id_to_name: Dict, failed_ids: List) -> str:
        """保存标题到文件"""
        file_path = FileHelper.get_output_path(
            "txt", f"{TimeHelper.format_time_filename()}.txt"
        )

        with open(file_path, "w", encoding="utf-8") as f:
            for id_value, title_data in results.items():
                # id | name 或 id
                name = id_to_name.get(id_value)
                if name and name != id_value:
                    f.write(f"{id_value} | {name}\n")
                else:
                    f.write(f"{id_value}\n")

                # 按排名排序标题
                sorted_titles = []
                for title, info in title_data.items():
                    cleaned_title = DataProcessor.clean_title(title)
                    if isinstance(info, dict):
                        ranks = info.get("ranks", [])
                        url = info.get("url", "")
                        mobile_url = info.get("mobileUrl", "")
                    else:
                        ranks = info if isinstance(info, list) else []
                        url = ""
                        mobile_url = ""

                    rank = ranks[0] if ranks else 1
                    sorted_titles.append((rank, cleaned_title, url, mobile_url))

                sorted_titles.sort(key=lambda x: x[0])

                for rank, cleaned_title, url, mobile_url in sorted_titles:
                    line = f"{rank}. {cleaned_title}"

                    if url:
                        line += f" [URL:{url}]"
                    if mobile_url:
                        line += f" [MOBILE:{mobile_url}]"
                    f.write(line + "\n")

                f.write("\n")

            if failed_ids:
                f.write("==== 以下ID请求失败 ====\n")
                for id_value in failed_ids:
                    f.write(f"{id_value}\n")

        return file_path

    @staticmethod
    def load_frequency_words(
        frequency_file: Optional[str] = None,
    ) -> Tuple[List[Dict], List[str]]:
        """加载频率词配置"""
        if frequency_file is None:
            frequency_file = os.environ.get(
                "FREQUENCY_WORDS_PATH", "config/frequency_words.txt"
            )

        frequency_path = Path(frequency_file)
        if not frequency_path.exists():
            raise FileNotFoundError(f"频率词文件 {frequency_file} 不存在")

        with open(frequency_path, "r", encoding="utf-8") as f:
            content = f.read()

        word_groups = [
            group.strip() for group in content.split("\n\n") if group.strip()
        ]

        processed_groups = []
        filter_words = []

        for group in word_groups:
            words = [word.strip() for word in group.split("\n") if word.strip()]

            group_required_words = []
            group_normal_words = []
            group_filter_words = []

            for word in words:
                if word.startswith("!"):
                    filter_words.append(word[1:])
                    group_filter_words.append(word[1:])
                elif word.startswith("+"):
                    group_required_words.append(word[1:])
                else:
                    group_normal_words.append(word)

            if group_required_words or group_normal_words:
                if group_normal_words:
                    group_key = " ".join(group_normal_words)
                else:
                    group_key = " ".join(group_required_words)

                processed_groups.append(
                    {
                        "required": group_required_words,
                        "normal": group_normal_words,
                        "group_key": group_key,
                    }
                )

        return processed_groups, filter_words

    @staticmethod
    def read_all_today_titles(
        current_platform_ids: Optional[List[str]] = None,
    ) -> Tuple[Dict, Dict, Dict]:
        """读取当天所有标题文件，支持按当前监控平台过滤"""
        date_folder = TimeHelper.format_date_folder()
        txt_dir = Path("output") / date_folder / "txt"

        if not txt_dir.exists():
            return {}, {}, {}

        all_results = {}
        final_id_to_name = {}
        title_info = {}

        files = sorted([f for f in txt_dir.iterdir() if f.suffix == ".txt"])

        for file_path in files:
            time_info = file_path.stem

            titles_by_id, file_id_to_name = DataProcessor._parse_file_titles(file_path)

            if current_platform_ids is not None:
                filtered_titles_by_id = {}
                filtered_id_to_name = {}

                for source_id, title_data in titles_by_id.items():
                    if source_id in current_platform_ids:
                        filtered_titles_by_id[source_id] = title_data
                        if source_id in file_id_to_name:
                            filtered_id_to_name[source_id] = file_id_to_name[source_id]

                titles_by_id = filtered_titles_by_id
                file_id_to_name = filtered_id_to_name

            final_id_to_name.update(file_id_to_name)

            for source_id, title_data in titles_by_id.items():
                DataProcessor._process_source_data(
                    source_id,
                    title_data,
                    time_info,
                    all_results,
                    title_info,
                )

        return all_results, final_id_to_name, title_info

    @staticmethod
    def _process_source_data(
        source_id: str,
        title_data: Dict,
        time_info: str,
        all_results: Dict,
        title_info: Dict,
    ) -> None:
        """处理来源数据，合并重复标题"""
        if source_id not in all_results:
            all_results[source_id] = title_data

            if source_id not in title_info:
                title_info[source_id] = {}

            for title, data in title_data.items():
                ranks = data.get("ranks", [])
                url = data.get("url", "")
                mobile_url = data.get("mobileUrl", "")

                title_info[source_id][title] = {
                    "first_time": time_info,
                    "last_time": time_info,
                    "count": 1,
                    "ranks": ranks,
                    "url": url,
                    "mobileUrl": mobile_url,
                }
        else:
            for title, data in title_data.items():
                ranks = data.get("ranks", [])
                url = data.get("url", "")
                mobile_url = data.get("mobileUrl", "")

                if title not in all_results[source_id]:
                    all_results[source_id][title] = {
                        "ranks": ranks,
                        "url": url,
                        "mobileUrl": mobile_url,
                    }
                    title_info[source_id][title] = {
                        "first_time": time_info,
                        "last_time": time_info,
                        "count": 1,
                        "ranks": ranks,
                        "url": url,
                        "mobileUrl": mobile_url,
                    }
                else:
                    existing_data = all_results[source_id][title]
                    existing_ranks = existing_data.get("ranks", [])
                    existing_url = existing_data.get("url", "")
                    existing_mobile_url = existing_data.get("mobileUrl", "")

                    merged_ranks = existing_ranks.copy()
                    for rank in ranks:
                        if rank not in merged_ranks:
                            merged_ranks.append(rank)

                    all_results[source_id][title] = {
                        "ranks": merged_ranks,
                        "url": existing_url or url,
                        "mobileUrl": existing_mobile_url or mobile_url,
                    }

                    title_info[source_id][title]["last_time"] = time_info
                    title_info[source_id][title]["ranks"] = merged_ranks
                    title_info[source_id][title]["count"] += 1
                    if not title_info[source_id][title].get("url"):
                        title_info[source_id][title]["url"] = url
                    if not title_info[source_id][title].get("mobileUrl"):
                        title_info[source_id][title]["mobileUrl"] = mobile_url


class StatisticsCalculator:
    """统计计算器"""

    @staticmethod
    def calculate_news_weight(
        title_data: Dict, rank_threshold: int = CONFIG["RANK_THRESHOLD"]
    ) -> float:
        """计算新闻权重，用于排序"""
        ranks = title_data.get("ranks", [])
        if not ranks:
            return 0.0

        count = title_data.get("count", len(ranks))
        weight_config = CONFIG["WEIGHT_CONFIG"]

        # 排名权重：Σ(11 - min(rank, 10)) / 出现次数
        rank_scores = []
        for rank in ranks:
            score = 11 - min(rank, 10)
            rank_scores.append(score)

        rank_weight = sum(rank_scores) / len(ranks) if ranks else 0

        # 频次权重：min(出现次数, 10) × 10
        frequency_weight = min(count, 10) * 10

        # 热度加成：高排名次数 / 总出现次数 × 100
        high_rank_count = sum(1 for rank in ranks if rank <= rank_threshold)
        hotness_ratio = high_rank_count / len(ranks) if ranks else 0
        hotness_weight = hotness_ratio * 100

        total_weight = (
            rank_weight * weight_config["RANK_WEIGHT"]
            + frequency_weight * weight_config["FREQUENCY_WEIGHT"]
            + hotness_weight * weight_config["HOTNESS_WEIGHT"]
        )

        return total_weight

    @staticmethod
    def sort_titles_by_weight(
        titles_list: List[Dict], rank_threshold: int = CONFIG["RANK_THRESHOLD"]
    ) -> List[Dict]:
        """按权重对新闻标题列表进行排序"""

        def get_sort_key(title_data):
            weight = StatisticsCalculator.calculate_news_weight(
                title_data, rank_threshold
            )
            ranks = title_data.get("ranks", [])
            count = title_data.get("count", 1)

            # 主要按权重排序，权重相同时按最高排名排序，再相同时按出现次数排序
            min_rank = min(ranks) if ranks else 999
            return -weight, min_rank, -count

        return sorted(titles_list, key=get_sort_key)

    @staticmethod
    def matches_word_groups(
        title: str, word_groups: List[Dict], filter_words: List[str]
    ) -> bool:
        """检查标题是否匹配词组规则"""
        title_lower = title.lower()

        # 过滤词检查
        if any(filter_word.lower() in title_lower for filter_word in filter_words):
            return False

        # 词组匹配检查
        for group in word_groups:
            required_words = group["required"]
            normal_words = group["normal"]

            # 必须词检查
            if required_words:
                all_required_present = all(
                    req_word.lower() in title_lower for req_word in required_words
                )
                if not all_required_present:
                    continue

            # 普通词检查
            if normal_words:
                any_normal_present = any(
                    normal_word.lower() in title_lower for normal_word in normal_words
                )
                if not any_normal_present:
                    continue

            return True

        return False

    @staticmethod
    def count_word_frequency(
        results: Dict,
        word_groups: List[Dict],
        filter_words: List[str],
        id_to_name: Dict,
        title_info: Optional[Dict] = None,
        rank_threshold: int = CONFIG["RANK_THRESHOLD"],
        new_titles: Optional[Dict] = None,
        mode: str = "daily",
    ) -> Tuple[List[Dict], int]:
        """统计词频，支持必须词、频率词、过滤词，并标记新增标题"""

        is_first_today = DataProcessor.is_first_crawl_today()

        # 确定处理的数据源和新增标记逻辑
        if mode == "incremental":
            if is_first_today:
                # 增量模式 + 当天第一次：处理所有新闻，都标记为新增
                results_to_process = results
                all_news_are_new = True
            else:
                # 增量模式 + 当天非第一次：只处理新增的新闻
                results_to_process = new_titles if new_titles else {}
                all_news_are_new = True
        elif mode == "current":
            # current 模式：只处理当前时间批次的新闻，但统计信息来自全部历史
            if title_info:
                latest_time = None
                for source_titles in title_info.values():
                    for title_data in source_titles.values():
                        last_time = title_data.get("last_time", "")
                        if last_time:
                            if latest_time is None or last_time > latest_time:
                                latest_time = last_time

                # 只处理 last_time 等于最新时间的新闻
                if latest_time:
                    results_to_process = {}
                    for source_id, source_titles in results.items():
                        if source_id in title_info:
                            filtered_titles = {}
                            for title, title_data in source_titles.items():
                                if title in title_info[source_id]:
                                    info = title_info[source_id][title]
                                    if info.get("last_time") == latest_time:
                                        filtered_titles[title] = title_data
                            if filtered_titles:
                                results_to_process[source_id] = filtered_titles

                    print(
                        f"当前榜单模式：最新时间 {latest_time}，筛选出 {sum(len(titles) for titles in results_to_process.values())} 条当前榜单新闻"
                    )
                else:
                    results_to_process = results
            else:
                results_to_process = results
            all_news_are_new = False
        else:
            # 当日汇总模式：处理所有新闻
            results_to_process = results
            all_news_are_new = False
            total_input_news = sum(len(titles) for titles in results.values())
            print(f"当日汇总模式：处理 {total_input_news} 条新闻")

        word_stats = {}
        total_titles = 0
        processed_titles = {}
        matched_new_count = 0

        if title_info is None:
            title_info = {}
        if new_titles is None:
            new_titles = {}

        for group in word_groups:
            group_key = group["group_key"]
            word_stats[group_key] = {"count": 0, "titles": {}}

        for source_id, titles_data in results_to_process.items():
            total_titles += len(titles_data)

            if source_id not in processed_titles:
                processed_titles[source_id] = {}

            for title, title_data in titles_data.items():
                if title in processed_titles.get(source_id, {}):
                    continue

                # 使用统一的匹配逻辑
                matches_frequency_words = StatisticsCalculator.matches_word_groups(
                    title, word_groups, filter_words
                )

                if not matches_frequency_words:
                    continue

                # 如果是增量模式或 current 模式第一次，统计匹配的新增新闻数量
                if (mode == "incremental" and all_news_are_new) or (
                    mode == "current" and is_first_today
                ):
                    matched_new_count += 1

                source_ranks = title_data.get("ranks", [])
                source_url = title_data.get("url", "")
                source_mobile_url = title_data.get("mobileUrl", "")

                # 找到匹配的词组
                title_lower = title.lower()
                for group in word_groups:
                    required_words = group["required"]
                    normal_words = group["normal"]

                    # 再次检查匹配
                    if required_words:
                        all_required_present = all(
                            req_word.lower() in title_lower
                            for req_word in required_words
                        )
                        if not all_required_present:
                            continue

                    if normal_words:
                        any_normal_present = any(
                            normal_word.lower() in title_lower
                            for normal_word in normal_words
                        )
                        if not any_normal_present:
                            continue

                    group_key = group["group_key"]
                    word_stats[group_key]["count"] += 1
                    if source_id not in word_stats[group_key]["titles"]:
                        word_stats[group_key]["titles"][source_id] = []

                    first_time = ""
                    last_time = ""
                    count_info = 1
                    ranks = source_ranks if source_ranks else []
                    url = source_url
                    mobile_url = source_mobile_url

                    # 对于 current 模式，从历史统计信息中获取完整数据
                    if (
                        mode == "current"
                        and title_info
                        and source_id in title_info
                        and title in title_info[source_id]
                    ):
                        info = title_info[source_id][title]
                        first_time = info.get("first_time", "")
                        last_time = info.get("last_time", "")
                        count_info = info.get("count", 1)
                        if "ranks" in info and info["ranks"]:
                            ranks = info["ranks"]
                        url = info.get("url", source_url)
                        mobile_url = info.get("mobileUrl", source_mobile_url)
                    elif (
                        title_info
                        and source_id in title_info
                        and title in title_info[source_id]
                    ):
                        info = title_info[source_id][title]
                        first_time = info.get("first_time", "")
                        last_time = info.get("last_time", "")
                        count_info = info.get("count", 1)
                        if "ranks" in info and info["ranks"]:
                            ranks = info["ranks"]
                        url = info.get("url", source_url)
                        mobile_url = info.get("mobileUrl", source_mobile_url)

                    if not ranks:
                        ranks = [99]

                    time_display = StatisticsCalculator._format_time_display(
                        first_time, last_time
                    )

                    source_name = id_to_name.get(source_id, source_id)

                    # 判断是否为新增
                    is_new = False
                    if all_news_are_new:
                        # 增量模式下所有处理的新闻都是新增，或者当天第一次的所有新闻都是新增
                        is_new = True
                    elif new_titles and source_id in new_titles:
                        # 检查是否在新增列表中
                        new_titles_for_source = new_titles[source_id]
                        is_new = title in new_titles_for_source

                    word_stats[group_key]["titles"][source_id].append(
                        {
                            "title": title,
                            "source_name": source_name,
                            "first_time": first_time,
                            "last_time": last_time,
                            "time_display": time_display,
                            "count": count_info,
                            "ranks": ranks,
                            "rank_threshold": rank_threshold,
                            "url": url,
                            "mobileUrl": mobile_url,
                            "is_new": is_new,
                        }
                    )

                    if source_id not in processed_titles:
                        processed_titles[source_id] = {}
                    processed_titles[source_id][title] = True
                    break

        # 最后统一打印汇总信息
        if mode == "incremental":
            if is_first_today:
                total_input_news = sum(len(titles) for titles in results.values())
                print(
                    f"增量模式：当天第一次爬取，{total_input_news} 条新闻中有 {matched_new_count} 条匹配频率词"
                )
            else:
                if new_titles:
                    total_new_count = sum(len(titles) for titles in new_titles.values())
                    print(
                        f"增量模式：{total_new_count} 条新增新闻中，有 {matched_new_count} 条匹配频率词"
                    )
                    if matched_new_count == 0:
                        print("增量模式：没有新增新闻匹配频率词，将不会发送通知")
                else:
                    print("增量模式：未检测到新增新闻")
        elif mode == "current":
            total_input_news = sum(
                len(titles) for titles in results_to_process.values()
            )
            if is_first_today:
                print(
                    f"当前榜单模式：当天第一次爬取，{total_input_news} 条当前榜单新闻中有 {matched_new_count} 条匹配频率词"
                )
            else:
                matched_count = sum(stat["count"] for stat in word_stats.values())
                print(
                    f"当前榜单模式：{total_input_news} 条当前榜单新闻中有 {matched_count} 条匹配频率词"
                )

        stats = []
        for group_key, data in word_stats.items():
            all_titles = []
            for source_id, title_list in data["titles"].items():
                all_titles.extend(title_list)

            sorted_titles = StatisticsCalculator.sort_titles_by_weight(
                all_titles, rank_threshold
            )

            stats.append(
                {
                    "word": group_key,
                    "count": data["count"],
                    "titles": sorted_titles,
                    "percentage": (
                        round(data["count"] / total_titles * 100, 2)
                        if total_titles > 0
                        else 0
                    ),
                }
            )

        stats.sort(key=lambda x: x["count"], reverse=True)
        return stats, total_titles

    @staticmethod
    def _format_rank_base(
        ranks: List[int], rank_threshold: int = 5, format_type: str = "html"
    ) -> str:
        """基础排名格式化方法"""
        if not ranks:
            return ""

        unique_ranks = sorted(set(ranks))
        min_rank = unique_ranks[0]
        max_rank = unique_ranks[-1]

        if format_type == "html":
            highlight_start = "<font color='red'><strong>"
            highlight_end = "</strong></font>"
        elif format_type == "feishu":
            highlight_start = "<font color='red'>**"
            highlight_end = "**</font>"
        elif format_type == "dingtalk":
            highlight_start = "**"
            highlight_end = "**"
        elif format_type == "wework":
            highlight_start = "**"
            highlight_end = "**"
        elif format_type == "telegram":
            highlight_start = "<b>"
            highlight_end = "</b>"
        else:
            highlight_start = "**"
            highlight_end = "**"

        if min_rank <= rank_threshold:
            if min_rank == max_rank:
                return f"{highlight_start}[{min_rank}]{highlight_end}"
            else:
                return f"{highlight_start}[{min_rank} - {max_rank}]{highlight_end}"
        else:
            if min_rank == max_rank:
                return f"[{min_rank}]"
            else:
                return f"[{min_rank} - {max_rank}]"

    @staticmethod
    def format_rank_for_html(ranks: List[int], rank_threshold: int = 5) -> str:
        """格式化HTML排名显示"""
        return StatisticsCalculator._format_rank_base(ranks, rank_threshold, "html")

    @staticmethod
    def format_rank_for_feishu(ranks: List[int], rank_threshold: int = 5) -> str:
        """格式化飞书排名显示"""
        return StatisticsCalculator._format_rank_base(ranks, rank_threshold, "feishu")

    @staticmethod
    def format_rank_for_dingtalk(ranks: List[int], rank_threshold: int = 5) -> str:
        """格式化钉钉排名显示"""
        return StatisticsCalculator._format_rank_base(ranks, rank_threshold, "dingtalk")

    @staticmethod
    def format_rank_for_wework(ranks: List[int], rank_threshold: int = 5) -> str:
        """格式化企业微信排名显示"""
        return StatisticsCalculator._format_rank_base(ranks, rank_threshold, "wework")

    @staticmethod
    def format_rank_for_telegram(ranks: List[int], rank_threshold: int = 5) -> str:
        """格式化Telegram排名显示"""
        return StatisticsCalculator._format_rank_base(ranks, rank_threshold, "telegram")

    @staticmethod
    def _format_time_display(first_time: str, last_time: str) -> str:
        """格式化时间显示"""
        if not first_time:
            return ""
        if first_time == last_time or not last_time:
            return first_time
        else:
            return f"[{first_time} ~ {last_time}]"


class ReportGenerator:
    """报告生成器"""

    @staticmethod
    def generate_html_report(
        stats: List[Dict],
        total_titles: int,
        failed_ids: Optional[List] = None,
        new_titles: Optional[Dict] = None,
        id_to_name: Optional[Dict] = None,
        mode: str = "daily",
        is_daily_summary: bool = False,
    ) -> str:
        """生成HTML报告"""
        if is_daily_summary:
            if mode == "current":
                filename = "当前榜单汇总.html"
            elif mode == "incremental":
                filename = "当日增量.html"
            else:
                filename = "当日汇总.html"
        else:
            filename = f"{TimeHelper.format_time_filename()}.html"

        file_path = FileHelper.get_output_path("html", filename)

        report_data = ReportGenerator._prepare_report_data(
            stats, failed_ids, new_titles, id_to_name, mode
        )

        html_content = ReportGenerator._render_html_content(
            report_data, total_titles, is_daily_summary, mode
        )

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        if is_daily_summary:
            root_file_path = Path("index.html")
            with open(root_file_path, "w", encoding="utf-8") as f:
                f.write(html_content)

        return file_path

    @staticmethod
    def _prepare_report_data(
        stats: List[Dict],
        failed_ids: Optional[List] = None,
        new_titles: Optional[Dict] = None,
        id_to_name: Optional[Dict] = None,
        mode: str = "daily",
    ) -> Dict:
        """准备报告数据"""
        processed_new_titles = []

        # 在增量模式下隐藏新增新闻区域
        hide_new_section = mode == "incremental"

        # 只有在非隐藏模式下才处理新增新闻部分
        if not hide_new_section:
            filtered_new_titles = {}
            if new_titles and id_to_name:
                word_groups, filter_words = DataProcessor.load_frequency_words()
                for source_id, titles_data in new_titles.items():
                    filtered_titles = ReportGenerator._apply_frequency_filter(
                        titles_data, word_groups, filter_words
                    )
                    if filtered_titles:
                        filtered_new_titles[source_id] = filtered_titles

            if filtered_new_titles and id_to_name:
                for source_id, titles_data in filtered_new_titles.items():
                    source_name = id_to_name.get(source_id, source_id)
                    source_titles = []

                    for title, title_data in titles_data.items():
                        url, mobile_url, ranks = (
                            ReportGenerator._extract_title_data_fields(title_data)
                        )

                        processed_title = {
                            "title": title,
                            "source_name": source_name,
                            "time_display": "",
                            "count": 1,
                            "ranks": ranks,
                            "rank_threshold": CONFIG["RANK_THRESHOLD"],
                            "url": url,
                            "mobile_url": mobile_url,
                            "is_new": True,
                        }
                        source_titles.append(processed_title)

                    if source_titles:
                        processed_new_titles.append(
                            {
                                "source_id": source_id,
                                "source_name": source_name,
                                "titles": source_titles,
                            }
                        )

        processed_stats = []
        for stat in stats:
            if stat["count"] <= 0:
                continue

            processed_titles = []
            for title_data in stat["titles"]:
                processed_title = {
                    "title": title_data["title"],
                    "source_name": title_data["source_name"],
                    "time_display": title_data["time_display"],
                    "count": title_data["count"],
                    "ranks": title_data["ranks"],
                    "rank_threshold": title_data["rank_threshold"],
                    "url": title_data.get("url", ""),
                    "mobile_url": title_data.get("mobileUrl", ""),
                    "is_new": title_data.get("is_new", False),
                }
                processed_titles.append(processed_title)

            processed_stats.append(
                {
                    "word": stat["word"],
                    "count": stat["count"],
                    "percentage": stat.get("percentage", 0),
                    "titles": processed_titles,
                }
            )

        return {
            "stats": processed_stats,
            "new_titles": processed_new_titles,
            "failed_ids": failed_ids or [],
            "total_new_count": sum(
                len(source["titles"]) for source in processed_new_titles
            ),
        }

    @staticmethod
    def _extract_title_data_fields(title_data) -> Tuple[str, str, List[int]]:
        """提取标题数据的通用字段"""
        url = title_data.get("url", "")
        mobile_url = title_data.get("mobileUrl", "")
        ranks = title_data.get("ranks", [])

        return url, mobile_url, ranks

    @staticmethod
    def _apply_frequency_filter(
        titles_data: Dict, word_groups: List[Dict], filter_words: List[str]
    ) -> Dict:
        """应用频率词过滤逻辑"""
        filtered_titles = {}

        for title, title_data in titles_data.items():
            if StatisticsCalculator.matches_word_groups(
                title, word_groups, filter_words
            ):
                filtered_titles[title] = title_data

        return filtered_titles

    @staticmethod
    def _html_escape(text: str) -> str:
        """HTML转义"""
        if not isinstance(text, str):
            text = str(text)

        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#x27;")
        )

    @staticmethod
    def _format_title_html(title_data: Dict) -> str:
        """格式化HTML标题显示"""
        rank_display = StatisticsCalculator.format_rank_for_html(
            title_data["ranks"], title_data["rank_threshold"]
        )

        link_url = title_data["mobile_url"] or title_data["url"]

        cleaned_title = DataProcessor.clean_title(title_data["title"])
        escaped_title = ReportGenerator._html_escape(cleaned_title)
        escaped_source_name = ReportGenerator._html_escape(title_data["source_name"])

        if link_url:
            escaped_url = ReportGenerator._html_escape(link_url)
            formatted_title = f'[{escaped_source_name}] <a href="{escaped_url}" target="_blank" class="news-link">{escaped_title}</a>'
        else:
            formatted_title = (
                f'[{escaped_source_name}] <span class="no-link">{escaped_title}</span>'
            )

        if rank_display:
            formatted_title += f" {rank_display}"
        if title_data["time_display"]:
            escaped_time = ReportGenerator._html_escape(title_data["time_display"])
            formatted_title += f" <font color='grey'>- {escaped_time}</font>"
        if title_data["count"] > 1:
            formatted_title += f" <font color='green'>({title_data['count']}次)</font>"

        if title_data["is_new"]:
            formatted_title = f"<div class='new-title'>🆕 {formatted_title}</div>"

        return formatted_title

    @staticmethod
    def _render_html_content(
        report_data: Dict,
        total_titles: int,
        is_daily_summary: bool = False,
        mode: str = "daily",
    ) -> str:
        """渲染HTML内容"""
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>频率词统计报告</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; }
                h1, h2 { color: #333; }
                table { border-collapse: collapse; width: 100%; margin-top: 20px; }
                th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
                th { background-color: #f2f2f2; }
                tr:nth-child(even) { background-color: #f9f9f9; }
                .word { font-weight: bold; }
                .count { text-align: center; }
                .percentage { text-align: center; }
                .titles { max-width: 500px; }
                .source { color: #666; font-style: italic; }
                .error { color: #d9534f; }
                .news-link { 
                    color: #007bff; 
                    text-decoration: none; 
                    border-bottom: 1px dotted #007bff;
                }
                .news-link:hover { 
                    color: #0056b3; 
                    text-decoration: underline; 
                }
                .news-link:visited { 
                    color: #6f42c1; 
                }
                .no-link { 
                    color: #333; 
                }
                .new-title {
                    background-color: #fff3cd;
                    border: 1px solid #ffc107;
                    border-radius: 3px;
                    padding: 2px 6px;
                    margin: 2px 0;
                }
                .new-section {
                    background-color: #d1ecf1;
                    border: 1px solid #bee5eb;
                    border-radius: 5px;
                    padding: 10px;
                    margin-top: 10px;
                }
                .new-section h3 {
                    color: #0c5460;
                    margin-top: 0;
                }
            </style>
        </head>
        <body>
            <h1>频率词统计报告</h1>
        """

        if is_daily_summary:
            if mode == "current":
                html += "<p>报告类型: 当前榜单模式</p>"
            elif mode == "incremental":
                html += "<p>报告类型: 增量模式</p>"
            else:
                html += "<p>报告类型: 当日汇总</p>"
        else:
            html += "<p>报告类型: 实时分析</p>"

        now = TimeHelper.get_beijing_time()
        html += f"<p>总标题数: {total_titles}</p>"
        html += f"<p>生成时间: {now.strftime('%Y-%m-%d %H:%M:%S')}</p>"

        if report_data["failed_ids"]:
            html += """
            <div class="error">
                <h2>请求失败的平台</h2>
                <ul>
            """
            for id_value in report_data["failed_ids"]:
                html += f"<li>{ReportGenerator._html_escape(id_value)}</li>"
            html += """
                </ul>
            </div>
            """

        html += """
            <table>
                <tr>
                    <th>排名</th>
                    <th>频率词</th>
                    <th>出现次数</th>
                    <th>占比</th>
                    <th>相关标题</th>
                </tr>
        """

        for i, stat in enumerate(report_data["stats"], 1):
            formatted_titles = []

            for title_data in stat["titles"]:
                formatted_title = ReportGenerator._format_title_html(title_data)
                formatted_titles.append(formatted_title)

            escaped_word = ReportGenerator._html_escape(stat["word"])
            html += f"""
                <tr>
                    <td>{i}</td>
                    <td class="word">{escaped_word}</td>
                    <td class="count">{stat['count']}</td>
                    <td class="percentage">{stat.get('percentage', 0)}%</td>
                    <td class="titles">{"<br>".join(formatted_titles)}</td>
                </tr>
            """

        html += """
            </table>
        """

        if report_data["new_titles"]:
            html += f"""
            <div class="new-section">
                <h3>🆕 本次新增热点新闻 (共 {report_data['total_new_count']} 条)</h3>
            """

            for source_data in report_data["new_titles"]:
                escaped_source = ReportGenerator._html_escape(
                    source_data["source_name"]
                )
                html += (
                    f"<h4>{escaped_source} ({len(source_data['titles'])} 条)</h4><ul>"
                )

                for title_data in source_data["titles"]:
                    title_data_copy = title_data.copy()
                    title_data_copy["is_new"] = False
                    formatted_title = ReportGenerator._format_title_html(
                        title_data_copy
                    )
                    if "] " in formatted_title:
                        formatted_title = formatted_title.split("] ", 1)[1]
                    html += f"<li>{formatted_title}</li>"

                html += "</ul>"

            html += "</div>"

        html += """
        </body>
        </html>
        """

        return html

    @staticmethod
    def _format_title_feishu(title_data: Dict, show_source: bool = True) -> str:
        """格式化飞书标题显示"""
        rank_display = StatisticsCalculator.format_rank_for_feishu(
            title_data["ranks"], title_data["rank_threshold"]
        )

        link_url = title_data["mobile_url"] or title_data["url"]

        cleaned_title = DataProcessor.clean_title(title_data["title"])

        if link_url:
            formatted_title = f"[{cleaned_title}]({link_url})"
        else:
            formatted_title = cleaned_title

        title_prefix = "🆕 " if title_data["is_new"] else ""

        if show_source:
            result = f"<font color='grey'>[{title_data['source_name']}]</font> {title_prefix}{formatted_title}"
        else:
            result = f"{title_prefix}{formatted_title}"

        if rank_display:
            result += f" {rank_display}"
        if title_data["time_display"]:
            result += f" <font color='grey'>- {title_data['time_display']}</font>"
        if title_data["count"] > 1:
            result += f" <font color='green'>({title_data['count']}次)</font>"

        return result

    @staticmethod
    def _format_title_dingtalk(title_data: Dict, show_source: bool = True) -> str:
        """格式化钉钉标题显示"""
        rank_display = StatisticsCalculator.format_rank_for_dingtalk(
            title_data["ranks"], title_data["rank_threshold"]
        )

        link_url = title_data["mobile_url"] or title_data["url"]

        cleaned_title = DataProcessor.clean_title(title_data["title"])

        if link_url:
            formatted_title = f"[{cleaned_title}]({link_url})"
        else:
            formatted_title = cleaned_title

        title_prefix = "🆕 " if title_data["is_new"] else ""

        if show_source:
            result = f"[{title_data['source_name']}] {title_prefix}{formatted_title}"
        else:
            result = f"{title_prefix}{formatted_title}"

        if rank_display:
            result += f" {rank_display}"
        if title_data["time_display"]:
            result += f" - {title_data['time_display']}"
        if title_data["count"] > 1:
            result += f" ({title_data['count']}次)"

        return result

    @staticmethod
    def _format_title_wework(title_data: Dict, show_source: bool = True) -> str:
        """格式化企业微信标题显示"""
        rank_display = StatisticsCalculator.format_rank_for_wework(
            title_data["ranks"], title_data["rank_threshold"]
        )

        link_url = title_data["mobile_url"] or title_data["url"]

        cleaned_title = DataProcessor.clean_title(title_data["title"])

        if link_url:
            formatted_title = f"[{cleaned_title}]({link_url})"
        else:
            formatted_title = cleaned_title

        title_prefix = "🆕 " if title_data["is_new"] else ""

        if show_source:
            result = f"[{title_data['source_name']}] {title_prefix}{formatted_title}"
        else:
            result = f"{title_prefix}{formatted_title}"

        if rank_display:
            result += f" {rank_display}"
        if title_data["time_display"]:
            result += f" - {title_data['time_display']}"
        if title_data["count"] > 1:
            result += f" ({title_data['count']}次)"

        return result

    @staticmethod
    def _format_title_telegram(title_data: Dict, show_source: bool = True) -> str:
        """格式化Telegram标题显示"""
        rank_display = StatisticsCalculator.format_rank_for_telegram(
            title_data["ranks"], title_data["rank_threshold"]
        )

        link_url = title_data["mobile_url"] or title_data["url"]

        cleaned_title = DataProcessor.clean_title(title_data["title"])

        if link_url:
            formatted_title = f'<a href="{link_url}">{ReportGenerator._html_escape(cleaned_title)}</a>'
        else:
            formatted_title = cleaned_title

        title_prefix = "🆕 " if title_data["is_new"] else ""

        if show_source:
            result = f"[{title_data['source_name']}] {title_prefix}{formatted_title}"
        else:
            result = f"{title_prefix}{formatted_title}"

        if rank_display:
            result += f" {rank_display}"
        if title_data["time_display"]:
            result += f" <code>- {title_data['time_display']}</code>"
        if title_data["count"] > 1:
            result += f" <code>({title_data['count']}次)</code>"

        return result

    @staticmethod
    def _render_feishu_content(
        report_data: Dict, update_info: Optional[Dict] = None, mode: str = "daily"
    ) -> str:
        """渲染飞书内容"""
        text_content = ""

        if report_data["stats"]:
            text_content += f"📊 **热点词汇统计**\n\n"

        total_count = len(report_data["stats"])

        for i, stat in enumerate(report_data["stats"]):
            word = stat["word"]
            count = stat["count"]

            sequence_display = f"<font color='grey'>[{i + 1}/{total_count}]</font>"

            if count >= 10:
                text_content += f"🔥 {sequence_display} **{word}** : <font color='red'>{count}</font> 条\n\n"
            elif count >= 5:
                text_content += f"📈 {sequence_display} **{word}** : <font color='orange'>{count}</font> 条\n\n"
            else:
                text_content += f"📌 {sequence_display} **{word}** : {count} 条\n\n"

            for j, title_data in enumerate(stat["titles"], 1):
                formatted_title = ReportGenerator._format_title_feishu(
                    title_data, show_source=True
                )
                text_content += f"  {j}. {formatted_title}\n"

                if j < len(stat["titles"]):
                    text_content += "\n"

            if i < len(report_data["stats"]) - 1:
                text_content += f"\n{CONFIG['FEISHU_MESSAGE_SEPARATOR']}\n\n"

        if not text_content:
            if mode == "incremental":
                mode_text = "增量模式下暂无新增匹配的热点词汇"
            elif mode == "current":
                mode_text = "当前榜单模式下暂无匹配的热点词汇"
            else:
                mode_text = "暂无匹配的热点词汇"
            text_content = f"📭 {mode_text}\n\n"

        if report_data["new_titles"]:
            if text_content and "暂无匹配" not in text_content:
                text_content += f"\n{CONFIG['FEISHU_MESSAGE_SEPARATOR']}\n\n"

            text_content += (
                f"🆕 **本次新增热点新闻** (共 {report_data['total_new_count']} 条)\n\n"
            )

            for source_data in report_data["new_titles"]:
                text_content += f"**{source_data['source_name']}** ({len(source_data['titles'])} 条):\n"

                for j, title_data in enumerate(source_data["titles"], 1):
                    title_data_copy = title_data.copy()
                    title_data_copy["is_new"] = False
                    formatted_title = ReportGenerator._format_title_feishu(
                        title_data_copy, show_source=False
                    )
                    text_content += f"  {j}. {formatted_title}\n"

                text_content += "\n"

        if report_data["failed_ids"]:
            if text_content and "暂无匹配" not in text_content:
                text_content += f"\n{CONFIG['FEISHU_MESSAGE_SEPARATOR']}\n\n"

            text_content += "⚠️ **数据获取失败的平台：**\n\n"
            for i, id_value in enumerate(report_data["failed_ids"], 1):
                text_content += f"  • <font color='red'>{id_value}</font>\n"

        now = TimeHelper.get_beijing_time()
        text_content += f"\n\n<font color='grey'>更新时间：{now.strftime('%Y-%m-%d %H:%M:%S')}</font>"

        if update_info:
            text_content += f"\n<font color='grey'>TrendRadar 发现新版本 {update_info['remote_version']}，当前 {update_info['current_version']}</font>"

        return text_content

    @staticmethod
    def _render_dingtalk_content(
        report_data: Dict, update_info: Optional[Dict] = None, mode: str = "daily"
    ) -> str:
        """渲染钉钉内容"""
        text_content = ""

        total_titles = sum(
            len(stat["titles"]) for stat in report_data["stats"] if stat["count"] > 0
        )
        now = TimeHelper.get_beijing_time()

        text_content += f"**总新闻数：** {total_titles}\n\n"
        text_content += f"**时间：** {now.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        text_content += f"**类型：** 热点分析报告\n\n"

        text_content += "---\n\n"

        if report_data["stats"]:
            text_content += f"📊 **热点词汇统计**\n\n"

            total_count = len(report_data["stats"])

            for i, stat in enumerate(report_data["stats"]):
                word = stat["word"]
                count = stat["count"]

                sequence_display = f"[{i + 1}/{total_count}]"

                if count >= 10:
                    text_content += (
                        f"🔥 {sequence_display} **{word}** : **{count}** 条\n\n"
                    )
                elif count >= 5:
                    text_content += (
                        f"📈 {sequence_display} **{word}** : **{count}** 条\n\n"
                    )
                else:
                    text_content += f"📌 {sequence_display} **{word}** : {count} 条\n\n"

                for j, title_data in enumerate(stat["titles"], 1):
                    formatted_title = ReportGenerator._format_title_dingtalk(
                        title_data, show_source=True
                    )
                    text_content += f"  {j}. {formatted_title}\n"

                    if j < len(stat["titles"]):
                        text_content += "\n"

                if i < len(report_data["stats"]) - 1:
                    text_content += f"\n---\n\n"

        if not report_data["stats"]:
            if mode == "incremental":
                mode_text = "增量模式下暂无新增匹配的热点词汇"
            elif mode == "current":
                mode_text = "当前榜单模式下暂无匹配的热点词汇"
            else:
                mode_text = "暂无匹配的热点词汇"
            text_content += f"📭 {mode_text}\n\n"

        if report_data["new_titles"]:
            if text_content and "暂无匹配" not in text_content:
                text_content += f"\n---\n\n"

            text_content += (
                f"🆕 **本次新增热点新闻** (共 {report_data['total_new_count']} 条)\n\n"
            )

            for source_data in report_data["new_titles"]:
                text_content += f"**{source_data['source_name']}** ({len(source_data['titles'])} 条):\n\n"

                for j, title_data in enumerate(source_data["titles"], 1):
                    title_data_copy = title_data.copy()
                    title_data_copy["is_new"] = False
                    formatted_title = ReportGenerator._format_title_dingtalk(
                        title_data_copy, show_source=False
                    )
                    text_content += f"  {j}. {formatted_title}\n"

                text_content += "\n"

        if report_data["failed_ids"]:
            if text_content and "暂无匹配" not in text_content:
                text_content += f"\n---\n\n"

            text_content += "⚠️ **数据获取失败的平台：**\n\n"
            for i, id_value in enumerate(report_data["failed_ids"], 1):
                text_content += f"  • **{id_value}**\n"

        text_content += f"\n\n> 更新时间：{now.strftime('%Y-%m-%d %H:%M:%S')}"

        if update_info:
            text_content += f"\n> TrendRadar 发现新版本 **{update_info['remote_version']}**，当前 **{update_info['current_version']}**"

        return text_content

    @staticmethod
    def _split_content_into_batches(
        report_data: Dict,
        format_type: str,
        update_info: Optional[Dict] = None,
        max_bytes: int = CONFIG["MESSAGE_BATCH_SIZE"],
        mode: str = "daily",
    ) -> List[str]:
        """分批处理消息内容，确保词组标题+至少第一条新闻的完整性"""
        batches = []

        total_titles = sum(
            len(stat["titles"]) for stat in report_data["stats"] if stat["count"] > 0
        )
        now = TimeHelper.get_beijing_time()

        base_header = ""
        if format_type == "wework":
            base_header = f"**总新闻数：** {total_titles}\n\n\n\n"
        elif format_type == "telegram":
            base_header = f"总新闻数： {total_titles}\n\n"

        base_footer = ""
        if format_type == "wework":
            base_footer = f"\n\n\n> 更新时间：{now.strftime('%Y-%m-%d %H:%M:%S')}"
            if update_info:
                base_footer += f"\n> TrendRadar 发现新版本 **{update_info['remote_version']}**，当前 **{update_info['current_version']}**"
        elif format_type == "telegram":
            base_footer = f"\n\n更新时间：{now.strftime('%Y-%m-%d %H:%M:%S')}"
            if update_info:
                base_footer += f"\nTrendRadar 发现新版本 {update_info['remote_version']}，当前 {update_info['current_version']}"

        stats_header = ""
        if report_data["stats"]:
            if format_type == "wework":
                stats_header = f"📊 **热点词汇统计**\n\n"
            elif format_type == "telegram":
                stats_header = f"📊 热点词汇统计\n\n"

        current_batch = base_header
        current_batch_has_content = False

        if (
            not report_data["stats"]
            and not report_data["new_titles"]
            and not report_data["failed_ids"]
        ):
            if mode == "incremental":
                mode_text = "增量模式下暂无新增匹配的热点词汇"
            elif mode == "current":
                mode_text = "当前榜单模式下暂无匹配的热点词汇"
            else:
                mode_text = "暂无匹配的热点词汇"
            simple_content = f"📭 {mode_text}\n\n"
            final_content = base_header + simple_content + base_footer
            batches.append(final_content)
            return batches

        # 处理热点词汇统计
        if report_data["stats"]:
            total_count = len(report_data["stats"])

            # 添加统计标题
            test_content = current_batch + stats_header
            if (
                len(test_content.encode("utf-8")) + len(base_footer.encode("utf-8"))
                < max_bytes
            ):
                current_batch = test_content
                current_batch_has_content = True
            else:
                if current_batch_has_content:
                    batches.append(current_batch + base_footer)
                current_batch = base_header + stats_header
                current_batch_has_content = True

            # 逐个处理词组（确保词组标题+第一条新闻的原子性）
            for i, stat in enumerate(report_data["stats"]):
                word = stat["word"]
                count = stat["count"]
                sequence_display = f"[{i + 1}/{total_count}]"

                # 构建词组标题
                word_header = ""
                if format_type == "wework":
                    if count >= 10:
                        word_header = (
                            f"🔥 {sequence_display} **{word}** : **{count}** 条\n\n"
                        )
                    elif count >= 5:
                        word_header = (
                            f"📈 {sequence_display} **{word}** : **{count}** 条\n\n"
                        )
                    else:
                        word_header = (
                            f"📌 {sequence_display} **{word}** : {count} 条\n\n"
                        )
                elif format_type == "telegram":
                    if count >= 10:
                        word_header = f"🔥 {sequence_display} {word} : {count} 条\n\n"
                    elif count >= 5:
                        word_header = f"📈 {sequence_display} {word} : {count} 条\n\n"
                    else:
                        word_header = f"📌 {sequence_display} {word} : {count} 条\n\n"

                # 构建第一条新闻
                first_news_line = ""
                if stat["titles"]:
                    first_title_data = stat["titles"][0]
                    if format_type == "wework":
                        formatted_title = ReportGenerator._format_title_wework(
                            first_title_data, show_source=True
                        )
                    elif format_type == "telegram":
                        formatted_title = ReportGenerator._format_title_telegram(
                            first_title_data, show_source=True
                        )
                    else:
                        formatted_title = f"{first_title_data['title']}"

                    first_news_line = f"  1. {formatted_title}\n"
                    if len(stat["titles"]) > 1:
                        first_news_line += "\n"

                # 原子性检查：词组标题+第一条新闻必须一起处理
                word_with_first_news = word_header + first_news_line
                test_content = current_batch + word_with_first_news

                if (
                    len(test_content.encode("utf-8")) + len(base_footer.encode("utf-8"))
                    >= max_bytes
                ):
                    # 当前批次容纳不下，开启新批次
                    if current_batch_has_content:
                        batches.append(current_batch + base_footer)
                    current_batch = base_header + stats_header + word_with_first_news
                    current_batch_has_content = True
                    start_index = 1
                else:
                    current_batch = test_content
                    current_batch_has_content = True
                    start_index = 1

                # 处理剩余新闻条目
                for j in range(start_index, len(stat["titles"])):
                    title_data = stat["titles"][j]
                    if format_type == "wework":
                        formatted_title = ReportGenerator._format_title_wework(
                            title_data, show_source=True
                        )
                    elif format_type == "telegram":
                        formatted_title = ReportGenerator._format_title_telegram(
                            title_data, show_source=True
                        )
                    else:
                        formatted_title = f"{title_data['title']}"

                    news_line = f"  {j + 1}. {formatted_title}\n"
                    if j < len(stat["titles"]) - 1:
                        news_line += "\n"

                    test_content = current_batch + news_line
                    if (
                        len(test_content.encode("utf-8"))
                        + len(base_footer.encode("utf-8"))
                        >= max_bytes
                    ):
                        if current_batch_has_content:
                            batches.append(current_batch + base_footer)
                        current_batch = (
                            base_header + stats_header + word_header + news_line
                        )
                        current_batch_has_content = True
                    else:
                        current_batch = test_content
                        current_batch_has_content = True

                # 词组间分隔符
                if i < len(report_data["stats"]) - 1:
                    separator = ""
                    if format_type == "wework":
                        separator = f"\n\n\n\n"
                    elif format_type == "telegram":
                        separator = f"\n\n"

                    test_content = current_batch + separator
                    if (
                        len(test_content.encode("utf-8"))
                        + len(base_footer.encode("utf-8"))
                        < max_bytes
                    ):
                        current_batch = test_content

        # 处理新增新闻（同样确保来源标题+第一条新闻的原子性）
        if report_data["new_titles"]:
            new_header = ""
            if format_type == "wework":
                new_header = f"\n\n\n\n🆕 **本次新增热点新闻** (共 {report_data['total_new_count']} 条)\n\n"
            elif format_type == "telegram":
                new_header = f"\n\n🆕 本次新增热点新闻 (共 {report_data['total_new_count']} 条)\n\n"

            test_content = current_batch + new_header
            if (
                len(test_content.encode("utf-8")) + len(base_footer.encode("utf-8"))
                >= max_bytes
            ):
                if current_batch_has_content:
                    batches.append(current_batch + base_footer)
                current_batch = base_header + new_header
                current_batch_has_content = True
            else:
                current_batch = test_content
                current_batch_has_content = True

            # 逐个处理新增新闻来源
            for source_data in report_data["new_titles"]:
                source_header = ""
                if format_type == "wework":
                    source_header = f"**{source_data['source_name']}** ({len(source_data['titles'])} 条):\n\n"
                elif format_type == "telegram":
                    source_header = f"{source_data['source_name']} ({len(source_data['titles'])} 条):\n\n"

                # 构建第一条新增新闻
                first_news_line = ""
                if source_data["titles"]:
                    first_title_data = source_data["titles"][0]
                    title_data_copy = first_title_data.copy()
                    title_data_copy["is_new"] = False

                    if format_type == "wework":
                        formatted_title = ReportGenerator._format_title_wework(
                            title_data_copy, show_source=False
                        )
                    elif format_type == "telegram":
                        formatted_title = ReportGenerator._format_title_telegram(
                            title_data_copy, show_source=False
                        )
                    else:
                        formatted_title = f"{title_data_copy['title']}"

                    first_news_line = f"  1. {formatted_title}\n"

                # 原子性检查：来源标题+第一条新闻
                source_with_first_news = source_header + first_news_line
                test_content = current_batch + source_with_first_news

                if (
                    len(test_content.encode("utf-8")) + len(base_footer.encode("utf-8"))
                    >= max_bytes
                ):
                    if current_batch_has_content:
                        batches.append(current_batch + base_footer)
                    current_batch = base_header + new_header + source_with_first_news
                    current_batch_has_content = True
                    start_index = 1
                else:
                    current_batch = test_content
                    current_batch_has_content = True
                    start_index = 1

                # 处理剩余新增新闻
                for j in range(start_index, len(source_data["titles"])):
                    title_data = source_data["titles"][j]
                    title_data_copy = title_data.copy()
                    title_data_copy["is_new"] = False

                    if format_type == "wework":
                        formatted_title = ReportGenerator._format_title_wework(
                            title_data_copy, show_source=False
                        )
                    elif format_type == "telegram":
                        formatted_title = ReportGenerator._format_title_telegram(
                            title_data_copy, show_source=False
                        )
                    else:
                        formatted_title = f"{title_data_copy['title']}"

                    news_line = f"  {j + 1}. {formatted_title}\n"

                    test_content = current_batch + news_line
                    if (
                        len(test_content.encode("utf-8"))
                        + len(base_footer.encode("utf-8"))
                        >= max_bytes
                    ):
                        if current_batch_has_content:
                            batches.append(current_batch + base_footer)
                        current_batch = (
                            base_header + new_header + source_header + news_line
                        )
                        current_batch_has_content = True
                    else:
                        current_batch = test_content
                        current_batch_has_content = True

                current_batch += "\n"

        if report_data["failed_ids"]:
            failed_header = ""
            if format_type == "wework":
                failed_header = f"\n\n\n\n⚠️ **数据获取失败的平台：**\n\n"
            elif format_type == "telegram":
                failed_header = f"\n\n⚠️ 数据获取失败的平台：\n\n"

            test_content = current_batch + failed_header
            if (
                len(test_content.encode("utf-8")) + len(base_footer.encode("utf-8"))
                >= max_bytes
            ):
                if current_batch_has_content:
                    batches.append(current_batch + base_footer)
                current_batch = base_header + failed_header
                current_batch_has_content = True
            else:
                current_batch = test_content
                current_batch_has_content = True

            for i, id_value in enumerate(report_data["failed_ids"], 1):
                failed_line = f"  • {id_value}\n"
                test_content = current_batch + failed_line
                if (
                    len(test_content.encode("utf-8")) + len(base_footer.encode("utf-8"))
                    >= max_bytes
                ):
                    if current_batch_has_content:
                        batches.append(current_batch + base_footer)
                    current_batch = base_header + failed_header + failed_line
                    current_batch_has_content = True
                else:
                    current_batch = test_content
                    current_batch_has_content = True

        # 完成最后批次
        if current_batch_has_content:
            batches.append(current_batch + base_footer)

        return batches

    @staticmethod
    def send_to_webhooks(
        stats: List[Dict],
        failed_ids: Optional[List] = None,
        report_type: str = "当日汇总",
        new_titles: Optional[Dict] = None,
        id_to_name: Optional[Dict] = None,
        update_info: Optional[Dict] = None,
        proxy_url: Optional[str] = None,
        mode: str = "daily",
    ) -> Dict[str, bool]:
        """发送数据到多个webhook平台"""
        results = {}

        report_data = ReportGenerator._prepare_report_data(
            stats, failed_ids, new_titles, id_to_name, mode
        )

        feishu_url = CONFIG["FEISHU_WEBHOOK_URL"]
        dingtalk_url = CONFIG["DINGTALK_WEBHOOK_URL"]
        wework_url = CONFIG["WEWORK_WEBHOOK_URL"]
        telegram_token = CONFIG["TELEGRAM_BOT_TOKEN"]
        telegram_chat_id = CONFIG["TELEGRAM_CHAT_ID"]

        update_info_to_send = update_info if CONFIG["SHOW_VERSION_UPDATE"] else None

        # 发送到飞书
        if feishu_url:
            results["feishu"] = ReportGenerator._send_to_feishu(
                feishu_url,
                report_data,
                report_type,
                update_info_to_send,
                proxy_url,
                mode,
            )

        # 发送到钉钉
        if dingtalk_url:
            results["dingtalk"] = ReportGenerator._send_to_dingtalk(
                dingtalk_url,
                report_data,
                report_type,
                update_info_to_send,
                proxy_url,
                mode,
            )

        # 发送到企业微信
        if wework_url:
            results["wework"] = ReportGenerator._send_to_wework(
                wework_url,
                report_data,
                report_type,
                update_info_to_send,
                proxy_url,
                mode,
            )

        # 发送到 Telegram
        if telegram_token and telegram_chat_id:
            results["telegram"] = ReportGenerator._send_to_telegram(
                telegram_token,
                telegram_chat_id,
                report_data,
                report_type,
                update_info_to_send,
                proxy_url,
                mode,
            )

        if not results:
            print("未配置任何webhook URL，跳过通知发送")

        return results

    @staticmethod
    def _send_to_feishu(
        webhook_url: str,
        report_data: Dict,
        report_type: str,
        update_info: Optional[Dict] = None,
        proxy_url: Optional[str] = None,
        mode: str = "daily",
    ) -> bool:
        """发送到飞书"""
        headers = {"Content-Type": "application/json"}

        text_content = ReportGenerator._render_feishu_content(
            report_data, update_info, mode
        )
        total_titles = sum(
            len(stat["titles"]) for stat in report_data["stats"] if stat["count"] > 0
        )

        now = TimeHelper.get_beijing_time()
        payload = {
            "msg_type": "text",
            "content": {
                "total_titles": total_titles,
                "timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
                "report_type": report_type,
                "text": text_content,
            },
        }

        proxies = None
        if proxy_url:
            proxies = {"http": proxy_url, "https": proxy_url}

        try:
            response = requests.post(
                webhook_url, headers=headers, json=payload, proxies=proxies, timeout=30
            )
            if response.status_code == 200:
                print(f"飞书通知发送成功 [{report_type}]")
                return True
            else:
                print(
                    f"飞书通知发送失败 [{report_type}]，状态码：{response.status_code}"
                )
                return False
        except Exception as e:
            print(f"飞书通知发送出错 [{report_type}]：{e}")
            return False

    @staticmethod
    def _send_to_dingtalk(
        webhook_url: str,
        report_data: Dict,
        report_type: str,
        update_info: Optional[Dict] = None,
        proxy_url: Optional[str] = None,
        mode: str = "daily",
    ) -> bool:
        """发送到钉钉"""
        headers = {"Content-Type": "application/json"}

        text_content = ReportGenerator._render_dingtalk_content(
            report_data, update_info, mode
        )

        payload = {
            "msgtype": "markdown",
            "markdown": {
                "title": f"TrendRadar 热点分析报告 - {report_type}",
                "text": text_content,
            },
        }

        proxies = None
        if proxy_url:
            proxies = {"http": proxy_url, "https": proxy_url}

        try:
            response = requests.post(
                webhook_url, headers=headers, json=payload, proxies=proxies, timeout=30
            )
            if response.status_code == 200:
                result = response.json()
                if result.get("errcode") == 0:
                    print(f"钉钉通知发送成功 [{report_type}]")
                    return True
                else:
                    print(
                        f"钉钉通知发送失败 [{report_type}]，错误：{result.get('errmsg')}"
                    )
                    return False
            else:
                print(
                    f"钉钉通知发送失败 [{report_type}]，状态码：{response.status_code}"
                )
                return False
        except Exception as e:
            print(f"钉钉通知发送出错 [{report_type}]：{e}")
            return False

    @staticmethod
    def _send_to_wework(
        webhook_url: str,
        report_data: Dict,
        report_type: str,
        update_info: Optional[Dict] = None,
        proxy_url: Optional[str] = None,
        mode: str = "daily",
    ) -> bool:
        """发送到企业微信（支持分批发送）"""
        headers = {"Content-Type": "application/json"}
        proxies = None
        if proxy_url:
            proxies = {"http": proxy_url, "https": proxy_url}

        # 获取分批内容
        batches = ReportGenerator._split_content_into_batches(
            report_data, "wework", update_info, mode=mode
        )

        print(f"企业微信消息分为 {len(batches)} 批次发送 [{report_type}]")

        # 逐批发送
        for i, batch_content in enumerate(batches, 1):
            batch_size = len(batch_content.encode("utf-8"))
            print(
                f"发送企业微信第 {i}/{len(batches)} 批次，大小：{batch_size} 字节 [{report_type}]"
            )

            # 添加批次标识
            if len(batches) > 1:
                batch_header = f"**[第 {i}/{len(batches)} 批次]**\n\n"
                batch_content = batch_header + batch_content

            payload = {"msgtype": "markdown", "markdown": {"content": batch_content}}

            try:
                response = requests.post(
                    webhook_url,
                    headers=headers,
                    json=payload,
                    proxies=proxies,
                    timeout=30,
                )
                if response.status_code == 200:
                    result = response.json()
                    if result.get("errcode") == 0:
                        print(
                            f"企业微信第 {i}/{len(batches)} 批次发送成功 [{report_type}]"
                        )
                        # 批次间间隔
                        if i < len(batches):
                            time.sleep(CONFIG["BATCH_SEND_INTERVAL"])
                    else:
                        print(
                            f"企业微信第 {i}/{len(batches)} 批次发送失败 [{report_type}]，错误：{result.get('errmsg')}"
                        )
                        return False
                else:
                    print(
                        f"企业微信第 {i}/{len(batches)} 批次发送失败 [{report_type}]，状态码：{response.status_code}"
                    )
                    return False
            except Exception as e:
                print(
                    f"企业微信第 {i}/{len(batches)} 批次发送出错 [{report_type}]：{e}"
                )
                return False

        print(f"企业微信所有 {len(batches)} 批次发送完成 [{report_type}]")
        return True

    @staticmethod
    def _send_to_telegram(
        bot_token: str,
        chat_id: str,
        report_data: Dict,
        report_type: str,
        update_info: Optional[Dict] = None,
        proxy_url: Optional[str] = None,
        mode: str = "daily",
    ) -> bool:
        """发送到Telegram（支持分批发送）"""
        headers = {"Content-Type": "application/json"}
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

        proxies = None
        if proxy_url:
            proxies = {"http": proxy_url, "https": proxy_url}

        # 获取分批内容
        batches = ReportGenerator._split_content_into_batches(
            report_data, "telegram", update_info, mode=mode
        )

        print(f"Telegram消息分为 {len(batches)} 批次发送 [{report_type}]")

        # 逐批发送
        for i, batch_content in enumerate(batches, 1):
            batch_size = len(batch_content.encode("utf-8"))
            print(
                f"发送Telegram第 {i}/{len(batches)} 批次，大小：{batch_size} 字节 [{report_type}]"
            )

            # 添加批次标识
            if len(batches) > 1:
                batch_header = f"<b>[第 {i}/{len(batches)} 批次]</b>\n\n"
                batch_content = batch_header + batch_content

            payload = {
                "chat_id": chat_id,
                "text": batch_content,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            }

            try:
                response = requests.post(
                    url, headers=headers, json=payload, proxies=proxies, timeout=30
                )
                if response.status_code == 200:
                    result = response.json()
                    if result.get("ok"):
                        print(
                            f"Telegram第 {i}/{len(batches)} 批次发送成功 [{report_type}]"
                        )
                        # 批次间间隔
                        if i < len(batches):
                            time.sleep(CONFIG["BATCH_SEND_INTERVAL"])
                    else:
                        print(
                            f"Telegram第 {i}/{len(batches)} 批次发送失败 [{report_type}]，错误：{result.get('description')}"
                        )
                        return False
                else:
                    print(
                        f"Telegram第 {i}/{len(batches)} 批次发送失败 [{report_type}]，状态码：{response.status_code}"
                    )
                    return False
            except Exception as e:
                print(
                    f"Telegram第 {i}/{len(batches)} 批次发送出错 [{report_type}]：{e}"
                )
                return False

        print(f"Telegram所有 {len(batches)} 批次发送完成 [{report_type}]")
        return True


@dataclass
class ModeStrategy:
    """模式策略配置"""

    mode_name: str
    description: str
    realtime_report_type: str
    summary_report_type: str
    should_send_realtime: bool
    should_generate_summary: bool
    summary_mode: str

    def get_log_messages(self) -> Dict[str, str]:
        """返回该模式的各种日志消息"""
        return {
            "mode_description": self.description,
            "realtime_skip": f"跳过实时推送通知：{self.mode_name}下未检测到匹配的新闻",
            "summary_skip": f"跳过{self.summary_report_type}通知：未匹配到有效的新闻内容",
        }


class NewsAnalyzer:
    """新闻分析器"""

    MODE_STRATEGIES = {
        "incremental": ModeStrategy(
            mode_name="增量模式",
            description="增量模式（只关注新增新闻，无新增时不推送）",
            realtime_report_type="实时增量",
            summary_report_type="当日汇总",
            should_send_realtime=True,
            should_generate_summary=True,
            summary_mode="daily",
        ),
        "current": ModeStrategy(
            mode_name="当前榜单模式",
            description="当前榜单模式（当前榜单匹配新闻 + 新增新闻区域 + 按时推送）",
            realtime_report_type="实时当前榜单",
            summary_report_type="当前榜单汇总",
            should_send_realtime=True,
            should_generate_summary=True,
            summary_mode="current",
        ),
        "daily": ModeStrategy(
            mode_name="当日汇总模式",
            description="当日汇总模式（所有匹配新闻 + 新增新闻区域 + 按时推送）",
            realtime_report_type="",
            summary_report_type="当日汇总",
            should_send_realtime=False,
            should_generate_summary=True,
            summary_mode="daily",
        ),
    }

    def __init__(
        self,
        request_interval: int = CONFIG["REQUEST_INTERVAL"],
        report_mode: str = CONFIG["REPORT_MODE"],
        rank_threshold: int = CONFIG["RANK_THRESHOLD"],
    ):
        self.request_interval = request_interval
        self.report_mode = report_mode
        self.rank_threshold = rank_threshold
        self.is_github_actions = os.environ.get("GITHUB_ACTIONS") == "true"
        self.is_docker_container = self._detect_docker_environment()
        self.update_info = None
        self.proxy_url = None
        self._setup_proxy()
        self.data_fetcher = DataFetcher(self.proxy_url)

        if self.is_github_actions:
            self._check_version_update()
    
    def _detect_docker_environment(self) -> bool:
        """检测是否运行在 Docker 容器中"""
        try:
            if os.environ.get("DOCKER_CONTAINER") == "true":
                return True
        
            if os.path.exists("/.dockerenv"):
                return True
            
            return False
        except Exception:
            return False
    
    def _should_open_browser(self) -> bool:
        """判断是否应该打开浏览器"""
        return not self.is_github_actions and not self.is_docker_container

    def _setup_proxy(self) -> None:
        """设置代理配置"""
        if not self.is_github_actions and CONFIG["USE_PROXY"]:
            self.proxy_url = CONFIG["DEFAULT_PROXY"]
            print("本地环境，使用代理")
        elif not self.is_github_actions and not CONFIG["USE_PROXY"]:
            print("本地环境，未启用代理")
        else:
            print("GitHub Actions环境，不使用代理")

    def _check_version_update(self) -> None:
        """检查版本更新"""
        try:
            need_update, remote_version = VersionChecker.check_for_updates(
                CONFIG["VERSION"], CONFIG["VERSION_CHECK_URL"], self.proxy_url
            )

            if need_update and remote_version:
                self.update_info = {
                    "current_version": CONFIG["VERSION"],
                    "remote_version": remote_version,
                }
                print(f"发现新版本: {remote_version} (当前: {CONFIG['VERSION']})")
            else:
                print("版本检查完成，当前为最新版本")
        except Exception as e:
            print(f"版本检查出错: {e}")

    def _get_mode_strategy(self) -> ModeStrategy:
        """获取当前模式的策略配置"""
        return self.MODE_STRATEGIES.get(self.report_mode, self.MODE_STRATEGIES["daily"])

    def _has_webhook_configured(self) -> bool:
        """检查是否配置了webhook"""
        return any(
            [
                CONFIG["FEISHU_WEBHOOK_URL"],
                CONFIG["DINGTALK_WEBHOOK_URL"],
                CONFIG["WEWORK_WEBHOOK_URL"],
                (CONFIG["TELEGRAM_BOT_TOKEN"] and CONFIG["TELEGRAM_CHAT_ID"]),
            ]
        )

    def _has_valid_content(
        self, stats: List[Dict], new_titles: Optional[Dict] = None
    ) -> bool:
        """检查是否有有效的新闻内容"""
        if self.report_mode in ["incremental", "current"]:
            # 增量模式和current模式下，只要stats有内容就说明有匹配的新闻
            return any(stat["count"] > 0 for stat in stats)
        else:
            # 当日汇总模式下，检查是否有匹配的频率词新闻或新增新闻
            has_matched_news = any(stat["count"] > 0 for stat in stats)
            has_new_news = bool(
                new_titles and any(len(titles) > 0 for titles in new_titles.values())
            )
            return has_matched_news or has_new_news

    def _load_analysis_data(
        self,
    ) -> Optional[Tuple[Dict, Dict, Dict, Dict, List, List]]:
        """统一的数据加载和预处理，使用当前监控平台列表过滤历史数据"""
        try:
            # 获取当前配置的监控平台ID列表
            current_platform_ids = []
            for platform in PLATFORMS:
                current_platform_ids.append(platform["id"])

            print(f"当前监控平台: {current_platform_ids}")

            all_results, id_to_name, title_info = DataProcessor.read_all_today_titles(
                current_platform_ids
            )

            if not all_results:
                print("没有找到当天的数据")
                return None

            total_titles = sum(len(titles) for titles in all_results.values())
            print(f"读取到 {total_titles} 个标题（已按当前监控平台过滤）")

            new_titles = DataProcessor.detect_latest_new_titles(current_platform_ids)
            word_groups, filter_words = DataProcessor.load_frequency_words()

            return (
                all_results,
                id_to_name,
                title_info,
                new_titles,
                word_groups,
                filter_words,
            )
        except Exception as e:
            print(f"数据加载失败: {e}")
            return None

    def _prepare_current_title_info(self, results: Dict, time_info: str) -> Dict:
        """从当前抓取结果构建标题信息"""
        title_info = {}
        for source_id, titles_data in results.items():
            title_info[source_id] = {}
            for title, title_data in titles_data.items():
                ranks = title_data.get("ranks", [])
                url = title_data.get("url", "")
                mobile_url = title_data.get("mobileUrl", "")

                title_info[source_id][title] = {
                    "first_time": time_info,
                    "last_time": time_info,
                    "count": 1,
                    "ranks": ranks,
                    "url": url,
                    "mobileUrl": mobile_url,
                }
        return title_info

    def _run_analysis_pipeline(
        self,
        data_source: Dict,
        mode: str,
        title_info: Dict,
        new_titles: Dict,
        word_groups: List[Dict],
        filter_words: List[str],
        id_to_name: Dict,
        failed_ids: Optional[List] = None,
        is_daily_summary: bool = False,
    ) -> Tuple[List[Dict], str]:
        """统一的分析流水线：数据处理 → 统计计算 → HTML生成"""

        # 统计计算
        stats, total_titles = StatisticsCalculator.count_word_frequency(
            data_source,
            word_groups,
            filter_words,
            id_to_name,
            title_info,
            self.rank_threshold,
            new_titles,
            mode=mode,
        )

        # HTML生成
        html_file = ReportGenerator.generate_html_report(
            stats,
            total_titles,
            failed_ids=failed_ids,
            new_titles=new_titles,
            id_to_name=id_to_name,
            mode=mode,
            is_daily_summary=is_daily_summary,
        )

        return stats, html_file

    def _send_notification_if_needed(
        self,
        stats: List[Dict],
        report_type: str,
        mode: str,
        failed_ids: Optional[List] = None,
        new_titles: Optional[Dict] = None,
        id_to_name: Optional[Dict] = None,
    ) -> bool:
        """统一的通知发送逻辑，包含所有判断条件"""
        has_webhook = self._has_webhook_configured()

        if (
            CONFIG["ENABLE_NOTIFICATION"]
            and has_webhook
            and self._has_valid_content(stats, new_titles)
        ):
            ReportGenerator.send_to_webhooks(
                stats,
                failed_ids or [],
                report_type,
                new_titles,
                id_to_name,
                self.update_info,
                self.proxy_url,
                mode=mode,
            )
            return True
        elif CONFIG["ENABLE_NOTIFICATION"] and not has_webhook:
            print("⚠️ 警告：通知功能已启用但未配置webhook URL，将跳过通知发送")
        elif not CONFIG["ENABLE_NOTIFICATION"]:
            print(f"跳过{report_type}通知：通知功能已禁用")
        elif (
            CONFIG["ENABLE_NOTIFICATION"]
            and has_webhook
            and not self._has_valid_content(stats, new_titles)
        ):
            mode_strategy = self._get_mode_strategy()
            log_messages = mode_strategy.get_log_messages()
            if "实时" in report_type:
                print(log_messages["realtime_skip"])
            else:
                print(log_messages["summary_skip"])

        return False

    def _generate_summary_report(self, mode_strategy: ModeStrategy) -> Optional[str]:
        """生成汇总报告（带通知）"""
        summary_type = (
            "当前榜单汇总" if mode_strategy.summary_mode == "current" else "当日汇总"
        )
        print(f"生成{summary_type}报告...")

        # 加载分析数据
        analysis_data = self._load_analysis_data()
        if not analysis_data:
            return None

        all_results, id_to_name, title_info, new_titles, word_groups, filter_words = (
            analysis_data
        )

        # 运行分析流水线
        stats, html_file = self._run_analysis_pipeline(
            all_results,
            mode_strategy.summary_mode,
            title_info,
            new_titles,
            word_groups,
            filter_words,
            id_to_name,
            is_daily_summary=True,
        )

        print(f"{summary_type}报告已生成: {html_file}")

        # 发送通知
        self._send_notification_if_needed(
            stats,
            mode_strategy.summary_report_type,
            mode_strategy.summary_mode,
            new_titles=new_titles,
            id_to_name=id_to_name,
        )

        return html_file

    def _generate_summary_html(self, mode: str = "daily") -> Optional[str]:
        """生成汇总HTML"""
        summary_type = "当前榜单汇总" if mode == "current" else "当日汇总"
        print(f"生成{summary_type}HTML...")

        # 加载分析数据
        analysis_data = self._load_analysis_data()
        if not analysis_data:
            return None

        all_results, id_to_name, title_info, new_titles, word_groups, filter_words = (
            analysis_data
        )

        # 运行分析流水线
        _, html_file = self._run_analysis_pipeline(
            all_results,
            mode,
            title_info,
            new_titles,
            word_groups,
            filter_words,
            id_to_name,
            is_daily_summary=True,
        )

        print(f"{summary_type}HTML已生成: {html_file}")
        return html_file

    def _initialize_and_check_config(self) -> None:
        """通用初始化和配置检查"""
        now = TimeHelper.get_beijing_time()
        print(f"当前北京时间: {now.strftime('%Y-%m-%d %H:%M:%S')}")

        if not CONFIG["ENABLE_CRAWLER"]:
            print("爬虫功能已禁用（ENABLE_CRAWLER=False），程序退出")
            return

        has_webhook = self._has_webhook_configured()
        if not CONFIG["ENABLE_NOTIFICATION"]:
            print("通知功能已禁用（ENABLE_NOTIFICATION=False），将只进行数据抓取")
        elif not has_webhook:
            print("未配置任何webhook URL，将只进行数据抓取，不发送通知")
        else:
            print("通知功能已启用，将发送webhook通知")

        mode_strategy = self._get_mode_strategy()
        print(f"报告模式: {self.report_mode}")
        print(f"运行模式: {mode_strategy.description}")

    def _crawl_data(self) -> Tuple[Dict, Dict, List]:
        """执行数据爬取"""
        ids = []
        for platform in PLATFORMS:
            if "name" in platform:
                ids.append((platform["id"], platform["name"]))
            else:
                ids.append(platform["id"])

        print(f"配置的监控平台: {[p.get('name', p['id']) for p in PLATFORMS]}")
        print(f"开始爬取数据，请求间隔 {self.request_interval} 毫秒")
        FileHelper.ensure_directory_exists("output")

        results, id_to_name, failed_ids = self.data_fetcher.crawl_websites(
            ids, self.request_interval
        )

        title_file = DataProcessor.save_titles_to_file(results, id_to_name, failed_ids)
        print(f"标题已保存到: {title_file}")

        return results, id_to_name, failed_ids

    def _execute_mode_strategy(
        self,
        mode_strategy: ModeStrategy,
        results: Dict,
        id_to_name: Dict,
        failed_ids: List,
    ) -> Optional[str]:
        """执行模式特定逻辑"""
        # 获取当前监控平台ID列表
        current_platform_ids = [platform["id"] for platform in PLATFORMS]

        new_titles = DataProcessor.detect_latest_new_titles(current_platform_ids)
        time_info = Path(
            DataProcessor.save_titles_to_file(results, id_to_name, failed_ids)
        ).stem
        word_groups, filter_words = DataProcessor.load_frequency_words()

        # current模式下，实时推送需要使用完整的历史数据来保证统计信息的完整性
        if self.report_mode == "current":
            # 加载完整的历史数据（已按当前平台过滤）
            analysis_data = self._load_analysis_data()
            if analysis_data:
                (
                    all_results,
                    historical_id_to_name,
                    historical_title_info,
                    historical_new_titles,
                    _,
                    _,
                ) = analysis_data

                print(
                    f"current模式：使用过滤后的历史数据，包含平台：{list(all_results.keys())}"
                )

                stats, html_file = self._run_analysis_pipeline(
                    all_results,
                    self.report_mode,
                    historical_title_info,
                    historical_new_titles,
                    word_groups,
                    filter_words,
                    historical_id_to_name,
                    failed_ids=failed_ids,
                )

                combined_id_to_name = {**historical_id_to_name, **id_to_name}

                print(f"HTML报告已生成: {html_file}")

                # 发送实时通知（使用完整历史数据的统计结果）
                summary_html = None
                if mode_strategy.should_send_realtime:
                    self._send_notification_if_needed(
                        stats,
                        mode_strategy.realtime_report_type,
                        self.report_mode,
                        failed_ids=failed_ids,
                        new_titles=historical_new_titles,
                        id_to_name=combined_id_to_name,
                    )
            else:
                print("❌ 严重错误：无法读取刚保存的数据文件")
                raise RuntimeError("数据一致性检查失败：保存后立即读取失败")
        else:
            title_info = self._prepare_current_title_info(results, time_info)
            stats, html_file = self._run_analysis_pipeline(
                results,
                self.report_mode,
                title_info,
                new_titles,
                word_groups,
                filter_words,
                id_to_name,
                failed_ids=failed_ids,
            )
            print(f"HTML报告已生成: {html_file}")

            # 发送实时通知（如果需要）
            summary_html = None
            if mode_strategy.should_send_realtime:
                self._send_notification_if_needed(
                    stats,
                    mode_strategy.realtime_report_type,
                    self.report_mode,
                    failed_ids=failed_ids,
                    new_titles=new_titles,
                    id_to_name=id_to_name,
                )

        # 生成汇总报告（如果需要）
        summary_html = None
        if mode_strategy.should_generate_summary:
            if mode_strategy.should_send_realtime:
                # 如果已经发送了实时通知，汇总只生成HTML不发送通知
                summary_html = self._generate_summary_html(mode_strategy.summary_mode)
            else:
                # daily模式：直接生成汇总报告并发送通知
                summary_html = self._generate_summary_report(mode_strategy)

        # 打开浏览器（仅在非容器环境）
        if self._should_open_browser() and html_file:
            if summary_html:
                summary_url = "file://" + str(Path(summary_html).resolve())
                print(f"正在打开汇总报告: {summary_url}")
                webbrowser.open(summary_url)
            else:
                file_url = "file://" + str(Path(html_file).resolve())
                print(f"正在打开HTML报告: {file_url}")
                webbrowser.open(file_url)
        elif self.is_docker_container and html_file:
            if summary_html:
                print(f"汇总报告已生成（Docker环境）: {summary_html}")
            else:
                print(f"HTML报告已生成（Docker环境）: {html_file}")

        return summary_html

    def run(self) -> None:
        """执行分析流程"""
        try:
            self._initialize_and_check_config()

            mode_strategy = self._get_mode_strategy()

            results, id_to_name, failed_ids = self._crawl_data()

            self._execute_mode_strategy(mode_strategy, results, id_to_name, failed_ids)

        except Exception as e:
            print(f"分析流程执行出错: {e}")
            raise


def main():
    try:
        analyzer = NewsAnalyzer(
            request_interval=CONFIG["REQUEST_INTERVAL"],
            report_mode=CONFIG["REPORT_MODE"],
            rank_threshold=CONFIG["RANK_THRESHOLD"],
        )
        analyzer.run()
    except FileNotFoundError as e:
        print(f"❌ 配置文件错误: {e}")
        print("\n请确保以下文件存在:")
        print("  • config/config.yaml")
        print("  • config/frequency_words.txt")
        print("\n参考项目文档进行正确配置")
    except Exception as e:
        print(f"❌ 程序运行错误: {e}")
        raise


if __name__ == "__main__":
    main()
