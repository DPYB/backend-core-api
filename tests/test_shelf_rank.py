import pytest

from app.core.shelf_rank import ShelfRank


def test_shelf_rank_initial():
    rank = ShelfRank.initial()
    assert rank == "V"


def test_shelf_rank_before():
    rank_v = ShelfRank.initial()  # "V"
    rank_before_v = ShelfRank.before(rank_v)
    assert rank_before_v < rank_v


def test_shelf_rank_after():
    rank_v = ShelfRank.initial()  # "V"
    rank_after_v = ShelfRank.after(rank_v)
    assert rank_v < rank_after_v


def test_shelf_rank_between():
    rank_a = "A"
    rank_c = "C"
    rank_b = ShelfRank.between(rank_a, rank_c)
    assert rank_a < rank_b < rank_c
    assert rank_b == "B"

    # 인접 문자 사이
    rank_a0 = "A"
    rank_a1 = "B"
    between_ab = ShelfRank.between(rank_a0, rank_a1)
    assert rank_a0 < between_ab < rank_a1


def test_shelf_rank_invalid_between():
    with pytest.raises(ValueError):
        ShelfRank.between("Z", "A")


def test_shelf_rank_rebalanced_sequence():
    ranks = ShelfRank.rebalanced_sequence(10)
    assert len(ranks) == 10
    # 모든 원소가 엄격하게 오름차순인지 확인
    for i in range(len(ranks) - 1):
        assert ranks[i] < ranks[i + 1]


def test_shelf_rank_rebalanced_sequence_large():
    ranks = ShelfRank.rebalanced_sequence(100)
    assert len(ranks) == 100
    for i in range(len(ranks) - 1):
        assert ranks[i] < ranks[i + 1]
