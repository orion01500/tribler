from twisted.internet.defer import inlineCallbacks, Deferred
from twisted.internet.task import LoopingCall

from Tribler.Test.Community.Market.Integration.test_market_base import TestMarketBase
from Tribler.community.market.core.quantity import Quantity
from Tribler.dispersy.candidate import Candidate
from Tribler.dispersy.util import blocking_call_on_reactor_thread


class TestMarketSession(TestMarketBase):
    """
    This class contains some integration tests for the market community.
    """

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def test_e2e_transaction(self):
        """
        test whether a full transaction will be executed between two nodes.
        """
        bid_session = yield self.create_session(1)
        test_deferred = Deferred()

        ask_community = self.market_communities[self.session]
        bid_community = self.market_communities[bid_session]

        @inlineCallbacks
        def on_tx_done(_):
            self.assertEqual(ask_community.wallets['DUM1'].balance, 1100)
            self.assertEqual(bid_community.wallets['DUM1'].balance, 900)

            balance_ask = yield ask_community.wallets['MC'].get_balance()
            balance_bid = yield bid_community.wallets['MC'].get_balance()
            self.assertEqual(balance_ask['available'], -10)
            self.assertEqual(balance_bid['available'], 10)

            # Verify whether everything is cleaned up correctly
            order_ask = ask_community.order_manager.order_repository.find_all()[0]
            order_bid = ask_community.order_manager.order_repository.find_all()[0]
            self.assertEqual(order_ask.reserved_quantity, Quantity(0, 'MC'))
            self.assertEqual(order_ask.traded_quantity, Quantity(10, 'MC'))
            self.assertEqual(order_bid.reserved_quantity, Quantity(0, 'MC'))
            self.assertEqual(order_bid.traded_quantity, Quantity(10, 'MC'))
            self.assertEqual(len(order_ask.reserved_ticks.keys()), 0)
            self.assertEqual(len(order_bid.reserved_ticks.keys()), 0)
            self.assertEqual(len(ask_community.order_book.asks), 0)
            self.assertEqual(len(ask_community.order_book.bids), 0)
            self.assertEqual(len(bid_community.order_book.asks), 0)
            self.assertEqual(len(bid_community.order_book.bids), 0)

        ask_community.add_discovered_candidate(
            Candidate(bid_session.get_dispersy_instance().lan_address, tunnel=False))
        bid_community.add_discovered_candidate(
            Candidate(self.session.get_dispersy_instance().lan_address, tunnel=False))
        yield self.async_sleep(10)
        bid_community.create_bid(10, 'DUM1', 10, 'MC', 3600)
        ask_community.create_ask(10, 'DUM1', 10, 'MC', 3600)

        ask_community.test_deferred.chainDeferred(test_deferred)
        bid_community.test_deferred.chainDeferred(test_deferred)
        yield test_deferred.addCallback(on_tx_done)

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def test_orderbook_sync(self):
        """
        Test whether the order book of two nodes are being synchronized
        """
        self.created_ask = False
        self.created_bid = False

        def check_orderbook_size():
            if len(ask_community.matchmakers) > 0 and not self.created_ask:
                ask_community.create_ask(10, 'DUM1', 2, 'DUM2', 3600)
                self.created_ask = True

            if len(ask_community.matchmakers) > 0 and not self.created_bid:
                bid_community.create_bid(1, 'DUM1', 2, 'DUM2', 3600)  # Does not match the ask
                self.created_bid = True

            if len(ask_community.order_book.bids) == 1 and len(bid_community.order_book.asks) == 1:
                check_lc.stop()
                test_deferred.callback(None)

        test_deferred = Deferred()
        bid_session = yield self.create_session(1)
        ask_community = self.market_communities[self.session]
        bid_community = self.market_communities[bid_session]

        ask_community.add_discovered_candidate(
            Candidate(bid_session.get_dispersy_instance().lan_address, tunnel=False))
        check_lc = LoopingCall(check_orderbook_size)
        check_lc.start(0.2)

        yield test_deferred
