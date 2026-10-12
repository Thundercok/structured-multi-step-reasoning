"""
rat.engine.curriculum_mapper — University Curriculum Code & Course Alias Expansion.
Provides bidirectional expansion between course codes (e.g. 501043, CO2003)
and canonical course titles (e.g. Kiến trúc máy tính, KienTrucMayTinh).
"""

from __future__ import annotations

import re
import unicodedata
from typing import Dict, List, Optional, Set, Union


def _normalize_alias(s: str) -> str:
    """Normalize string for robust token matching."""
    s = unicodedata.normalize("NFD", s.lower())
    s = re.sub(r"[\u0300-\u036f]", "", s)  # strip accents
    s = re.sub(r"[^a-z0-9]", "", s)       # strip punctuation and spaces
    return s


# Core curriculum database (Bidirectional clusters)
_CURRICULUM_CLUSTERS = [
    {
        "primary_code": "501043",
        "alt_codes": ["CO2003", "CE2003", "KTMT"],
        "names": ["Kiến trúc máy tính", "Kien truc may tinh", "KienTrucMayTinh", "Computer Architecture", "CompArch"],
    },
    {
        "primary_code": "501042",
        "alt_codes": ["CO2001", "CE2001", "HDH"],
        "names": ["Hệ điều hành", "He dieu hanh", "HeDieuHanh", "Operating Systems", "OS"],
    },
    {
        "primary_code": "502044",
        "alt_codes": ["CO3005", "CE3005", "MMT"],
        "names": ["Mạng máy tính", "Mang may tinh", "MangMayTinh", "Computer Networks", "Networking"],
    },
    {
        "primary_code": "501044",
        "alt_codes": ["CO1007", "CE1007", "DSA", "CTDL"],
        "names": ["Cấu trúc dữ liệu và giải thuật", "Cau truc du lieu va giai thuat", "CauTrucDuLieu", "Data Structures", "Algorithms"],
    },
    {
        "primary_code": "502047",
        "alt_codes": ["CO2013", "CSDL", "DBMS"],
        "names": ["Cơ sở dữ liệu", "Co so du lieu", "CoSoDuLieu", "Database Systems", "Database"],
    },
    {
        "primary_code": "502070",
        "alt_codes": ["CO3061", "AI", "TTNT"],
        "names": ["Trí tuệ nhân tạo", "Tri tue nhan tao", "TriTueNhanTao", "Artificial Intelligence"],
    },
    {
        "primary_code": "501011",
        "alt_codes": ["MT1003", "GT1", "CALC1"],
        "names": ["Giải tích 1", "Giai tich 1", "GiaiTich1", "Calculus 1", "Calculus"],
    },
    {
        "primary_code": "501012",
        "alt_codes": ["MT1005", "GT2", "CALC2"],
        "names": ["Giải tích 2", "Giai tich 2", "GiaiTich2", "Calculus 2"],
    },
    {
        "primary_code": "501013",
        "alt_codes": ["MT1007", "DSTT", "LINALG"],
        "names": ["Đại số tuyến tính", "Dai so tuyen tinh", "DaiSoTuyenTinh", "Linear Algebra"],
    },
    {
        "primary_code": "501015",
        "alt_codes": ["PH1003", "VL1", "PHYS1"],
        "names": ["Vật lý 1", "Vat ly 1", "VatLy1", "General Physics 1"],
    },
    {
        "primary_code": "501017",
        "alt_codes": ["PH1007", "VL2", "PHYS2"],
        "names": ["Vật lý 2", "Vat ly 2", "VatLy2", "General Physics 2"],
    },
    {
        "primary_code": "501002",
        "alt_codes": ["CO1005", "NMLT", "PROG1"],
        "names": ["Nhập môn lập trình", "Nhap mon lap trinh", "NhapMonLapTrinh", "Intro to Programming"],
    },
    {
        "primary_code": "502046",
        "alt_codes": ["CO2011", "OOP", "LTHDT"],
        "names": ["Lập trình hướng đối tượng", "Lap trinh huong doi tuong", "LapTrinhHuongDoiTuong", "Object Oriented Programming"],
    },
    {
        "primary_code": "502061",
        "alt_codes": ["CO3001", "CNPM", "SE"],
        "names": ["Công nghệ phần mềm", "Cong nghe phan mem", "CongNghePhanMem", "Software Engineering"],
    },
    {
        "primary_code": "502049",
        "alt_codes": ["CO2017", "LTDT"],
        "names": ["Lý thuyết đồ thị", "Ly thuyet do thi", "LyThuyetDoThi", "Graph Theory"],
    },
    {
        "primary_code": "502045",
        "alt_codes": ["CO2007", "HTN"],
        "names": ["Hệ thống nhúng", "He thong nhung", "HeThongNhung", "Embedded Systems"],
    },
    {
        "primary_code": "503049",
        "alt_codes": ["CO3093", "MMTNC"],
        "names": ["Mạng máy tính nâng cao", "Mang may tinh nang cao", "MangMayTinhNangCao", "Advanced Computer Networks"],
    },
    {
        "primary_code": "502048",
        "alt_codes": ["CO3007", "PTTKHT", "SAD"],
        "names": ["Phân tích thiết kế hệ thống", "Phan tich thiet ke he thong", "PhanTichThietKeHeThong", "Systems Analysis and Design"],
    },
    {
        "primary_code": "501004",
        "alt_codes": ["CO1009", "KTLT"],
        "names": ["Kỹ thuật lập trình", "Ky thuat lap trinh", "KyThuatLapTrinh", "Programming Techniques"],
    },
    {
        "primary_code": "502043",
        "alt_codes": ["CO2009", "KTDH", "CG"],
        "names": ["Kỹ thuật đồ họa", "Ky thuat do hoa", "KyThuatDoHoa", "Computer Graphics"],
    },
    {
        "primary_code": "501014",
        "alt_codes": ["MT2013", "XSTK", "PROB"],
        "names": ["Xác suất thống kê", "Xac suat thong ke", "XacSuatThongKe", "Probability and Statistics"],
    },
    {
        "primary_code": "502068",
        "alt_codes": ["CO3065", "PTUDDD", "PTUDD", "MAD"],
        "names": ["Phát triển ứng dụng di động", "Phat trien ung dung di dong", "PhatTrienUngDungDiDong", "Mobile Application Development"],
    },
    {
        "primary_code": "502050",
        "alt_codes": ["CO3059", "ANM", "NETSEC"],
        "names": ["An ninh mạng", "An ninh mang", "AnNinhMang", "Network Security"],
    },
    {
        "primary_code": "502052",
        "alt_codes": ["CO3043", "HTTT", "IS"],
        "names": ["Hệ thống thông tin", "He thong thong tin", "HeThongThongTin", "Information Systems"],
    },
]


def generate_acronym(text: str) -> str:
    """Generate initials-based acronym from words (e.g. 'Phân tích thiết kế hệ thống' -> 'pttkht')."""
    if not text:
        return ""
    # Split PascalCase / camelCase before lowercase
    spaced = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
    spaced = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", spaced)
    text_norm = unicodedata.normalize("NFD", spaced.lower())
    text_clean = "".join(ch for ch in text_norm if unicodedata.category(ch) != "Mn")
    text_clean = text_clean.replace("đ", "d").replace("Đ", "D")
    words = re.findall(r"[a-z0-9]+", text_clean)
    return "".join(w[0] for w in words if w)


def damerau_levenshtein_le_1(s1: str, s2: str) -> bool:
    """Check if Damerau-Levenshtein distance between s1 and s2 is <= 1 (insertion, deletion, substitution, transposition)."""
    if s1 == s2:
        return True
    len1, len2 = len(s1), len(s2)
    if abs(len1 - len2) > 1:
        return False
    if len1 == len2:
        diffs = [i for i in range(len1) if s1[i] != s2[i]]
        if len(diffs) == 1:
            return True  # 1 substitution
        if len(diffs) == 2 and diffs[1] == diffs[0] + 1:
            return s1[diffs[0]] == s2[diffs[1]] and s1[diffs[1]] == s2[diffs[0]]  # 1 adjacent transposition
        return False
    longer, shorter = (s1, s2) if len1 > len2 else (s2, s1)
    for i in range(len(longer)):
        if longer[:i] + longer[i + 1 :] == shorter:
            return True
    return False


class CurriculumMapper:
    """Fast in-memory index for curriculum aliases, course codes, and acronyms with typo tolerance."""

    def __init__(self) -> None:
        # Map normalized key -> cluster dict
        self._lookup: Dict[str, dict] = {}
        self._build_index()

    def _build_index(self) -> None:
        for cluster in _CURRICULUM_CLUSTERS:
            # Register primary code
            prim = cluster["primary_code"]
            self._lookup[_normalize_alias(prim)] = cluster

            # Register alternate codes
            for alt in cluster["alt_codes"]:
                self._lookup[_normalize_alias(alt)] = cluster

            # Register names & dynamic initials-based acronyms
            for name in cluster["names"]:
                norm_n = _normalize_alias(name)
                if len(norm_n) >= 4:
                    self._lookup[norm_n] = cluster

                # Register initials-based acronym (e.g. 'pttkht', 'ktlt')
                acr = generate_acronym(name)
                if 2 <= len(acr) <= 7:
                    self._lookup[acr] = cluster

    def find_cluster(self, token_or_phrase: str, allow_typo: bool = True) -> Optional[dict]:
        """Find curriculum cluster matching a token, course code or title with Levenshtein <= 1 typo tolerance."""
        cluster, _ = self.find_cluster_with_correction(token_or_phrase, allow_typo=allow_typo)
        return cluster

    def find_cluster_with_correction(self, token_or_phrase: str, allow_typo: bool = True) -> Tuple[Optional[dict], Optional[str]]:
        """Return (cluster, canonical_key) with automatic Levenshtein <= 1 typo correction for keys >= 4 chars."""
        key = _normalize_alias(token_or_phrase)
        if not key:
            return None, None
        exact = self._lookup.get(key)
        if exact:
            return exact, key

        if allow_typo and len(key) >= 4:
            for candidate_key, cluster in self._lookup.items():
                if abs(len(candidate_key) - len(key)) <= 1:
                    if damerau_levenshtein_le_1(key, candidate_key):
                        return cluster, candidate_key
        return None, None

    def expand(self, query: str) -> List[str]:
        """
        Analyze a query and return matching aliases for any detected courses.
        Example: '501043' -> ['CO2003', 'KienTrucMayTinh', 'Kiến trúc máy tính', 'Architecture']
        """
        expansions: Set[str] = set()
        q_clean = query.strip()
        if not q_clean:
            return []

        # Check full query match
        cluster, matched_key = self.find_cluster_with_correction(q_clean)
        if cluster:
            self._add_cluster_expansions(cluster, expansions, exclude=matched_key or q_clean)
            return sorted(list(expansions))

        # Check sub-tokens (e.g. course codes like 501043 or CO2003)
        tokens = re.findall(r"[A-Za-z0-9_]+", q_clean)
        for t in tokens:
            if len(t) >= 4:
                c = self.find_cluster(t)
                if c:
                    self._add_cluster_expansions(c, expansions, exclude=t)

        # Check 2-word and 3-word n-grams for course titles (e.g. 'kien truc may tinh')
        words = q_clean.split()
        for n in (3, 2):
            for i in range(len(words) - n + 1):
                phrase = " ".join(words[i:i + n])
                c = self.find_cluster(phrase)
                if c:
                    self._add_cluster_expansions(c, expansions, exclude=phrase)

        return sorted(list(expansions))

    def _add_cluster_expansions(self, cluster: dict, target: Set[str], exclude: str) -> None:
        norm_exc = _normalize_alias(exclude)
        # Add primary code
        if _normalize_alias(cluster["primary_code"]) != norm_exc:
            target.add(cluster["primary_code"])
        # Add alt codes
        for code in cluster["alt_codes"]:
            if _normalize_alias(code) != norm_exc:
                target.add(code)
        # Add compact names and titles
        for name in cluster["names"]:
            if _normalize_alias(name) != norm_exc:
                target.add(name)


curriculum_mapper = CurriculumMapper()
