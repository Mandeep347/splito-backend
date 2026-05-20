"""
BalanceService owns two responsibilities:

1. update_balances_for_expense  — called atomically inside expense creation/reversal
2. simplify_debts               — O(n log n) greedy min/max-heap simplification
"""
import heapq
import uuid
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.balance.models import BalanceCache
from app.repositories.balance_repository import BalanceCacheRepository


class BalanceService:
    def __init__(self, db: AsyncSession) -> None:
        self.repo = BalanceCacheRepository(db)

    # ── Balance mutation ──────────────────────────────────────────────────────

    async def apply_expense(
        self,
        group_id: uuid.UUID,
        paid_by: uuid.UUID,
        debts: list[tuple[uuid.UUID, Decimal]],   # (debtor_id, owed_amount)
        currency: str,
    ) -> None:
        """
        For each debtor who is NOT the payer:
          - debtor owes payer  → increase debtor→payer balance
          - payer is owed      → decrease payer→debtor balance (mirror)
        Convention: positive balance_amount = user_id owes other_user_id
        """
        for debtor_id, amount in debts:
            if debtor_id == paid_by:
                continue  # payer's share doesn't create a debt
            await self.repo.upsert(group_id, debtor_id, paid_by, amount)
            await self.repo.upsert(group_id, paid_by, debtor_id, -amount)

    async def reverse_expense(
        self,
        group_id: uuid.UUID,
        paid_by: uuid.UUID,
        debts: list[tuple[uuid.UUID, Decimal]],
    ) -> None:
        """Mirror of apply_expense — subtracts instead of adds."""
        for debtor_id, amount in debts:
            if debtor_id == paid_by:
                continue
            await self.repo.upsert(group_id, debtor_id, paid_by, -amount)
            await self.repo.upsert(group_id, paid_by, debtor_id, amount)

    async def apply_settlement(
        self,
        group_id: uuid.UUID,
        from_user_id: uuid.UUID,
        to_user_id: uuid.UUID,
        amount: Decimal,
    ) -> None:
        """from_user pays to_user → reduce from_user's debt."""
        await self.repo.upsert(group_id, from_user_id, to_user_id, -amount)
        await self.repo.upsert(group_id, to_user_id, from_user_id, amount)

    # ── Balance reads ─────────────────────────────────────────────────────────

    async def get_group_balances(self, group_id: uuid.UUID) -> list[BalanceCache]:
        rows = await self.repo.get_group_balances(group_id)
        # Only return meaningful (non-zero) positive-direction rows
        return [r for r in rows if Decimal(str(r.balance_amount)) > Decimal("0.005")]

    async def get_user_net_balance(
        self, group_id: uuid.UUID, user_id: uuid.UUID
    ) -> Decimal:
        rows = await self.repo.get_group_balances(group_id)
        total = Decimal("0")
        for r in rows:
            if r.user_id == user_id:
                total += Decimal(str(r.balance_amount))
        return total

    async def get_user_all_group_balances(self, user_id: uuid.UUID) -> list[BalanceCache]:
        return await self.repo.get_user_balances_all_groups(user_id)

    # ── Debt simplification ───────────────────────────────────────────────────

    async def simplify(self, group_id: uuid.UUID) -> list[tuple[uuid.UUID, uuid.UUID, Decimal]]:
        """
        Reduce pairwise debts to the minimum number of transactions.
        Returns list of (debtor_id, creditor_id, amount).

        Algorithm:
          1. Compute net balance per person (positive = creditor, negative = debtor)
          2. Use two heaps: max-heap of creditors, min-heap (negated) of debtors
          3. Greedily settle largest debt against largest credit
          Complexity: O(n log n)
        """
        rows = await self.repo.get_group_balances(group_id)

        # Aggregate net per user (sum all rows where user_id = X)
        net: dict[uuid.UUID, Decimal] = {}
        for r in rows:
            uid = r.user_id
            net[uid] = net.get(uid, Decimal("0")) + Decimal(str(r.balance_amount))

        # creditors: net < 0 (they are owed money, i.e., others owe them)
        # debtors:   net > 0 (they owe money)
        # Wait — convention: positive = user owes other.
        # So net[user] > 0  means user is a net debtor
        #    net[user] < 0  means user is a net creditor

        creditors: list[tuple[Decimal, uuid.UUID]] = []  # max-heap (negate for Python)
        debtors:   list[tuple[Decimal, uuid.UUID]] = []  # max-heap (negate)

        for uid, balance in net.items():
            if balance > Decimal("0.005"):
                heapq.heappush(debtors, (-balance, uid))
            elif balance < Decimal("-0.005"):
                heapq.heappush(creditors, (balance, uid))  # already negative → min-heap = max credit

        transactions: list[tuple[uuid.UUID, uuid.UUID, Decimal]] = []

        while debtors and creditors:
            debt_neg, debtor = heapq.heappop(debtors)
            debt = -debt_neg

            cred_neg, creditor = heapq.heappop(creditors)
            credit = -cred_neg  # how much creditor is owed

            settled = min(debt, credit)
            transactions.append((debtor, creditor, settled.quantize(Decimal("0.01"))))

            remainder_debt = debt - settled
            remainder_credit = credit - settled

            if remainder_debt > Decimal("0.005"):
                heapq.heappush(debtors, (-remainder_debt, debtor))
            if remainder_credit > Decimal("0.005"):
                heapq.heappush(creditors, (-remainder_credit, creditor))

        return transactions
