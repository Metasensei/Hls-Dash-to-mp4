import os
import requests
from tqdm import tqdm
import xml.etree.ElementTree as ET
import m3u8
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests


def calculate_hls_size(url):
    """
    HLS faylining umumiy hajmini hisoblaydi.

    Args:
        url (str): HLS (m3u8) faylining URL' manzili.

    Returns:
        float: Umumiy hajm MB'da.
    """
    try:
        playlist = m3u8.load(url)
        total_size = 0

        for segment in playlist.segments:
            if segment.byterange_length:
                total_size += segment.byterange_length
            else:
                # Agar byterange_length ko'rsatilmagan bo'lsa, segmentni yuklab o'lchash
                segment_response = requests.head(segment.uri, timeout=10)
                if segment_response.status_code == 200:
                    segment_size = int(segment_response.headers.get("content-length", 0))
                    total_size += segment_size

        return round(total_size / (1024 * 1024), 2)  # MB
    except Exception as e:
        print(f"❌ HLS hajmini hisoblashda xatolik: {e}")
        return 0.0
# MPD hajmini hisoblash

def calculate_total_size(url, format_type):
    """
    URL bo'yicha umumiy hajmni hisoblaydi.

    Args:
        url (str): Fayl URL' manzili.
        format_type (str): "mpd" yoki "hls" format turi.

    Returns:
        float: Umumiy hajm MB'da.
    """
    if format_type == "mpd":
        return calculate_mpd_size(url)
    elif format_type == "hls":
        return calculate_hls_size(url)
    else:
        raise ValueError("Noma'lum format turi: Faqat 'mpd' yoki 'hls' qabul qilinadi.")


def extract_segment_urls(url, format_type):
    """
    MPD yoki HLS URL'lar uchun segment URL'larini qaytaradi.
    """
    if format_type == "mpd":
        return extract_mpd_segments(url)
    elif format_type == "hls":
        return extract_hls_segments(url)
    else:
        raise ValueError("Noto‘g‘ri format turi. Faqat 'mpd' yoki 'hls' qabul qilinadi.")

def extract_mpd_segments(url):
    """
    MPD fayldan segment URL'larini ajratib olish.
    """
    response = requests.get(url)
    if response.status_code != 200:
        raise ValueError(f"❌ MPD faylni yuklab bo‘lmadi: {url}")

    root = ET.fromstring(response.content)
    namespace = {'ns': 'urn:mpeg:dash:schema:mpd:2011'}

    base_url = url.rsplit('/', 1)[0] + '/'
    segment_urls = []

    adaptation_sets = root.findall(".//ns:AdaptationSet[@contentType='video']", namespace)
    for adaptation in adaptation_sets:
        for representation in adaptation.findall("ns:Representation", namespace):
            representation_id = representation.attrib.get('id', '')
            segment_template = representation.find("ns:SegmentTemplate", namespace)
            if not segment_template:
                continue

            media_template = segment_template.attrib.get('media', '')
            start_number = int(segment_template.attrib.get('startNumber', 1))
            timeline = segment_template.find("ns:SegmentTimeline", namespace)

            if timeline:
                current_number = start_number
                for segment in timeline.findall("ns:S", namespace):
                    duration = int(segment.attrib.get('d', 0))
                    repeat_count = int(segment.attrib.get('r', 0))

                    for _ in range(repeat_count + 1):
                        segment_url = media_template.replace('$RepresentationID$', representation_id).replace('$Number%05d$', f"{current_number:05}")
                        segment_urls.append(base_url + segment_url)
                        current_number += 1

    return segment_urls

def extract_hls_segments(url):
    """
    HLS fayldan segment URL'larini ajratib olish.
    """
    import m3u8
    playlist = m3u8.load(url)
    segment_urls = [segment.absolute_uri for segment in playlist.segments]
    return segment_urls
def calculate_mpd_size(url):
    response = requests.get(url)
    if response.status_code != 200:
        print(f"❌ MPD faylni yuklab bo'lmadi: {url}")
        return None

    root = ET.fromstring(response.content)
    namespace = {'ns': 'urn:mpeg:dash:schema:mpd:2011'}
    total_size = 0

    adaptation_sets = root.findall(".//ns:AdaptationSet[@contentType='video']", namespace)
    for adaptation in adaptation_sets:
        for representation in adaptation.findall("ns:Representation", namespace):
            bandwidth = int(representation.attrib.get('bandwidth', 0))  # bit/s
            segment_template = representation.find("ns:SegmentTemplate", namespace)
            if segment_template is None:
                continue
            timeline = segment_template.find("ns:SegmentTimeline", namespace)
            if timeline is None:
                continue

            timescale = int(segment_template.attrib.get('timescale', 1))
            duration = 0
            for segment in timeline.findall("ns:S", namespace):
                d = int(segment.attrib['d'])
                r = int(segment.attrib.get('r', 0))
                duration += d * (r + 1)

            total_size += (bandwidth * (duration / timescale)) / (8 * 1024 * 1024)  # MB

    return round(total_size, 2)


# Segment URL'larini MPD formatidan ajratish
def extract_mpd_segments(url):
    response = requests.get(url)
    if response.status_code != 200:
        print(f"❌ MPD faylni yuklab bo'lmadi: {url}")
        return []

    root = ET.fromstring(response.content)
    namespace = {'ns': 'urn:mpeg:dash:schema:mpd:2011'}
    base_url = url.rsplit('/', 1)[0] + '/'

    segments = []
    adaptation_sets = root.findall(".//ns:AdaptationSet[@contentType='video']", namespace)
    for adaptation in adaptation_sets:
        for representation in adaptation.findall("ns:Representation", namespace):
            representation_id = representation.attrib['id']
            segment_template = representation.find("ns:SegmentTemplate", namespace)
            if segment_template is None:
                continue
            timeline = segment_template.find("ns:SegmentTimeline", namespace)
            if timeline is None:
                continue

            media = segment_template.attrib.get('media')
            start_number = int(segment_template.attrib.get('startNumber', 1))
            current_number = start_number

            for segment in timeline.findall("ns:S", namespace):
                duration = int(segment.attrib['d'])
                repeat = int(segment.attrib.get('r', 0))
                for _ in range(repeat + 1):
                    segment_url = media.replace("$RepresentationID$", representation_id).replace("$Number%05d$", f"{current_number:05}")
                    segments.append(base_url + segment_url)
                    current_number += 1

    return segments


# HLS segment URL'larini olish
def extract_hls_segments(url):
    playlist = m3u8.load(url)
    return [segment.absolute_uri for segment in playlist.segments]


# Segmentlarni yuklab olish va birlashtirish
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests

def download_segments(segments, output_file, total_size):
    """
    Segmentlarni yuklab olish va birlashtirish.
    """
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    downloaded_size = 0

    with open(output_file, "wb") as final_file:
        for i, segment_url in enumerate(segments):
            response = requests.get(segment_url, stream=True)
            if response.status_code == 200:
                file_size = int(response.headers.get('content-length', 0))
                with tqdm(
                    desc=f"⬇️ Segment {i + 1}/{len(segments)}",
                    total=file_size,
                    unit='B',
                    unit_scale=True,
                    unit_divisor=1024
                ) as bar:
                    for chunk in response.iter_content(chunk_size=1024):
                        final_file.write(chunk)
                        bar.update(len(chunk))
                        downloaded_size += len(chunk)
                percent_complete = (downloaded_size / (total_size * 1024 * 1024)) * 100
                print(f"⬇️ Umumiy yuklash: {percent_complete:.2f}% | Yuklangan: {downloaded_size / (1024 * 1024):.2f} MB")
            else:
                print(f"⚠️ Segment yuklashda xatolik: {segment_url}")

    print(f"✅ Yuklash tugadi. Fayl saqlandi: {output_file}")

def parallel_download_segments(segment_urls, temp_dir, max_workers=4):
    os.makedirs(temp_dir, exist_ok=True)
    segment_paths = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_segment = {
            executor.submit(download_segments, url, temp_dir, i): i
            for i, url in enumerate(segment_urls)
        }

        for future in as_completed(future_to_segment):
            try:
                segment_path = future.result()
                segment_paths.append(segment_path)
            except Exception as e:
                print(f"⚠️ Segment yuklashda xatolik: {e}")
    
    return segment_paths


# Asosiy funksiya
def main():
    url = input("🎬 URL kiriting (MPD yoki HLS): ")

    if url.endswith(".mpd"):
        size = calculate_mpd_size(url)
        print(f"📊 Umumiy hajm: {size} MB")
        format_type = "mpd"
    elif url.endswith(".m3u8"):
        size = calculate_hls_size(url)
        print(f"📊 Umumiy hajm: {size} MB")
        format_type = "hls"
    else:
        print("❌ Faqat MPD yoki HLS URL'lari qabul qilinadi.")
        return

    confirmation = input("⬇️ Yuklashni boshlashni xohlaysizmi? (y/n): ").strip().lower()
    if confirmation == "y":
        output_file = "downloads/output_final.mp4"
        segments = extract_segment_urls(url, format_type)  # Format turini uzatamiz
        download_segments(segments, output_file, size)
    else:
        print("❌ Yuklash bekor qilindi.")

if __name__ == "__main__":
    main()