class ShelfRankExhaustedException(Exception):
    """키 공간이 128자를 초과하여 재분배(rebalance)가 필요한 경우 발생"""

    pass


class ShelfRank:
    """
    책장 내 도서 순서를 효율적으로 정렬하고 재배열하기 위한 62진수 기반 문자열 랭크(LexoRank) 알고리즘.
    """

    ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
    BASE = len(ALPHABET)
    MAX_LENGTH = 128

    @classmethod
    def initial(cls) -> str:
        return cls.ALPHABET[cls.BASE // 2]  # 'V'

    @classmethod
    def before(cls, next_rank: str) -> str:
        return cls.between(None, next_rank)

    @classmethod
    def after(cls, prev_rank: str) -> str:
        return cls.between(prev_rank, None)

    @classmethod
    def between(cls, prev_rank: str | None, next_rank: str | None) -> str:
        if prev_rank is not None and next_rank is not None and prev_rank >= next_rank:
            raise ValueError(
                f"prev는 next보다 사전식으로 앞서야 합니다: prev={prev_rank}, next={next_rank}"
            )

        result = []
        upper_unbounded = next_rank is None
        i = 0

        while True:
            low = (
                cls.ALPHABET.index(prev_rank[i])
                if (prev_rank and i < len(prev_rank))
                else 0
            )
            high = (
                cls.BASE
                if upper_unbounded
                else (
                    cls.ALPHABET.index(next_rank[i])
                    if (next_rank and i < len(next_rank))
                    else 0
                )
            )

            if high - low > 1:
                mid = low + (high - low) // 2
                result.append(cls.ALPHABET[mid])
                return "".join(result)

            result.append(cls.ALPHABET[low])
            if high - low == 1:
                upper_unbounded = True
            i += 1

            if len(result) >= cls.MAX_LENGTH:
                raise ShelfRankExhaustedException()

    @classmethod
    def rebalanced_sequence(cls, count: int) -> list[str]:
        if count <= 0:
            return []

        digit_count = 1
        capacity = cls.BASE
        while capacity < count * 4:
            digit_count += 1
            capacity *= cls.BASE

        result = []
        for i in range(count):
            pos = ((i + 1) * capacity) // (count + 1)
            result.append(cls._to_key(pos, digit_count))
        return result

    @classmethod
    def _to_key(cls, position: int, digit_count: int) -> str:
        chars = []
        rem = position
        for _ in range(digit_count):
            chars.append(cls.ALPHABET[rem % cls.BASE])
            rem //= cls.BASE
        chars.reverse()

        while len(chars) > 1 and chars[-1] == cls.ALPHABET[0]:
            chars.pop()
        return "".join(chars)
