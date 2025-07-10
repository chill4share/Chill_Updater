# Utils/ffmpeg_utils.py

import os
import sys
import subprocess
import psutil
import shutil
import json
# <--- THAY ĐỔI Ở ĐÂY --->
from .logger_setup import LoggerProvider
logger = LoggerProvider.get_logger('ffmpeg')


def setup_ffmpeg(asset_path):
    """Thiết lập FFmpeg và trả về đường dẫn tới ffmpeg.exe."""
    ffmpeg_path = None
    # Sử dụng asset_path được truyền vào thay vì tự tính toán
    ffmpeg_dir = os.path.join(asset_path, 'ffmpeg')

    local_ffmpeg_path = os.path.join(ffmpeg_dir, 'ffmpeg.exe')
    if os.path.exists(local_ffmpeg_path):
        logger.info("Đã tìm thấy FFmpeg trong thư mục 'ffmpeg' của dự án.")
        ffmpeg_path = local_ffmpeg_path
    else:
        logger.warning(f"Không tìm thấy ffmpeg.exe trong '{ffmpeg_dir}', thử tìm trong PATH hệ thống.")
        ffmpeg_path = shutil.which("ffmpeg")
        if ffmpeg_path:
            logger.info("Đã tìm thấy FFmpeg trong PATH hệ thống.")
        else:
            logger.warning("Không tìm thấy FFmpeg trong PATH hệ thống.")

    if not ffmpeg_path:
        error_msg = (
            "Không tìm thấy FFmpeg. Vui lòng tải và đặt 'ffmpeg.exe' vào thư mục 'ffmpeg' "
            "cùng cấp với file main.py, hoặc thêm vào biến môi trường PATH."
        )
        logger.error(error_msg)
        raise FileNotFoundError(error_msg)

    ffmpeg_path = os.path.normpath(ffmpeg_path)

    if not os.access(ffmpeg_path, os.X_OK):
        error_msg = f"Không có quyền thực thi FFmpeg tại {ffmpeg_path}."
        logger.error(error_msg)
        raise PermissionError(error_msg)

    os.environ["FFMPEG_PATH"] = ffmpeg_path
    logger.info(f"Đường dẫn FFmpeg được thiết lập: {ffmpeg_path}")
    return ffmpeg_path

def run_ffmpeg(input_file, output_file, args, recording_id='N/A'):
    ffmpeg_path = os.environ.get("FFMPEG_PATH")
    if not ffmpeg_path:
        raise FileNotFoundError("Đường dẫn FFmpeg chưa được thiết lập.")
    
    # --- THAY ĐỔI: Xây dựng câu lệnh linh hoạt ---
    cmd = [ffmpeg_path]
    # Chỉ thêm tham số -i nếu input_file được cung cấp
    if input_file:
        cmd.extend(["-i", input_file])
    
    # Thêm các tham số còn lại
    cmd.extend(args)
    # Thêm tham số output và -y để tự động ghi đè
    cmd.extend(["-y", output_file])
    
    try:
        process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW, text=True, encoding='utf-8', errors='ignore'
        )
        stdout, stderr = process.communicate()
        if process.returncode != 0:
            error_msg = stderr if stderr else "Lỗi không xác định"
            logger.error(f"Lỗi FFmpeg: {error_msg.strip()}", extra={'recording_id': recording_id})
            raise Exception(f"Lỗi FFmpeg: {error_msg.strip()}")
        logger.info(f"Thao tác FFmpeg với file {os.path.basename(output_file)} thành công", extra={'recording_id': recording_id})
        # Trả về PID để có thể quản lý nếu cần
        return process.pid
    except Exception as e:
        logger.error(f"Lỗi chạy FFmpeg: {e}", extra={'recording_id': recording_id})
        raise

def stop_ffmpeg_processes(pid_list):
    for pid in pid_list[:]:
        try:
            if psutil.pid_exists(pid):
                proc = psutil.Process(pid)
                if 'ffmpeg' in proc.name().lower():
                    proc.kill()
                    logger.info(f"Đã dừng tiến trình FFmpeg (PID: {pid})")
                pid_list.remove(pid)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            if pid in pid_list:
                pid_list.remove(pid)
        except Exception as e:
            logger.error(f"Lỗi khi dừng FFmpeg (PID: {pid}): {e}")

def get_media_duration(file_path):
    """
    Sử dụng ffprobe để lấy tổng thời lượng (giây) của một file media.
    Trả về duration dưới dạng float, hoặc None nếu có lỗi.
    """
    ffmpeg_dir = os.path.dirname(os.environ.get("FFMPEG_PATH", "ffmpeg.exe"))
    ffprobe_path = os.path.join(ffmpeg_dir, "ffprobe.exe")

    if not os.path.exists(ffprobe_path):
        logger.error(f"Không tìm thấy ffprobe.exe tại '{ffprobe_path}'")
        return None

    command = [
        ffprobe_path,
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        file_path
    ]

    try:
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8',
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        if result.returncode != 0:
            logger.error(f"Lỗi khi chạy ffprobe: {result.stderr}")
            return None

        data = json.loads(result.stdout)
        duration = float(data['format']['duration'])
        logger.info(f"Lấy được thời lượng file '{os.path.basename(file_path)}': {duration:.2f} giây.")
        return duration

    except (FileNotFoundError, json.JSONDecodeError, KeyError, ValueError) as e:
        logger.error(f"Không thể lấy thời lượng file '{file_path}': {e}", exc_info=True)
        return None

