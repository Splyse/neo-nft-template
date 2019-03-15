# To run these tests:
# python3 -m unittest test_nft.py

from boa_test.tests.boa_test import BoaFixtureTest
from boa.compiler import Compiler
from neo.Core.TX.Transaction import Transaction
from neo.Prompt.Commands.BuildNRun import TestBuild
from neo.EventHub import events
from neo.SmartContract.SmartContractEvent import SmartContractEvent, NotifyEvent
from neo.Settings import settings
from neo.Prompt.Utils import parse_param
from neo.Core.FunctionCode import FunctionCode
from neocore.Fixed8 import Fixed8
from nft_template import *

import shutil
import os
from logzero import logger

settings.USE_DEBUG_STORAGE = True
settings.DEBUG_STORAGE_PATH = './fixtures/debugstorage'
settings.log_smart_contract_events = True
settings.emit_notify_events_on_sc_execution_error = True


class TestContract(BoaFixtureTest):

    dispatched_events = []
    dispatched_logs = []

    @classmethod
    def tearDownClass(cls):
        super(BoaFixtureTest, cls).tearDownClass()
        try:
            if os.path.exists(settings.debug_storage_leveldb_path):

                shutil.rmtree(settings.debug_storage_leveldb_path)
            else:
                logger.error("debug storage path doesn't exist")
        except Exception as e:
            logger.error("couldn't remove debug storage %s " % e)

    @classmethod
    def setUpClass(cls):
        super(TestContract, cls).setUpClass()

        def on_notif(evt):
            print(evt)
            cls.dispatched_events.append(evt)
            print("dispatched events %s " % cls.dispatched_events)

        def on_log(evt):
            print(evt)
            cls.dispatched_logs.append(evt)
        events.on(SmartContractEvent.RUNTIME_NOTIFY, on_notif)
        events.on(SmartContractEvent.RUNTIME_LOG, on_log)
        print("1:{}\n2:{}\n3:{}\n".format(BoaFixtureTest.wallet_1_script_hash.Data,
              BoaFixtureTest.wallet_2_script_hash.Data,
              BoaFixtureTest.wallet_3_script_hash.Data))

    def test_NFT_1(self):

        output = Compiler.instance().load('nft_template.py').default
        out = output.write()

        tx, results, total_ops, engine = TestBuild(out, ['name', '[]'], self.GetWallet1(), '0710', '05')
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].GetString(), TOKEN_NAME)

        tx, results, total_ops, engine = TestBuild(out, ['symbol', '[]'], self.GetWallet1(), '0710', '05')
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].GetString(), TOKEN_SYMBOL)

        tx, results, total_ops, engine = TestBuild(out, ['decimals', '[]'], self.GetWallet1(), '0710', '05')
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].GetBigInteger(), TOKEN_DECIMALS)

        tx, results, total_ops, engine = TestBuild(out, ['nonexistentmethod', '[]'], self.GetWallet1(), '0710', '05')
        self.assertEqual(len(results), 0)

	# mint a token
        owner = bytearray(TOKEN_CONTRACT_OWNER)
        tx, results, total_ops, engine = TestBuild(out, ['mintToken', parse_param([owner,1,'token1ROData','https://example.com/images/1.png','token1ROData'])], self.GetWallet1(), '0710', '05')
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].GetBoolean(), True)

        # now circulation should be equal to 1
        tx, results, total_ops, engine = TestBuild(out, ['totalSupply', '[]'], self.GetWallet1(), '0710', '05')
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].GetBigInteger(), 1)

        # now the owner should have a balance of 1
        tx, results, total_ops, engine = TestBuild(out, ['balanceOf', parse_param([bytearray(TOKEN_CONTRACT_OWNER)])], self.GetWallet1(), '0710', '05')
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].GetBigInteger(), 1)

    def test_NFT_2(self):

        output = Compiler.instance().load('nft_template.py').default
        out = output.write()

        # now transfer tokens to wallet 2

        TestContract.dispatched_events = []

        test_transfer_id = 1
        tx, results, total_ops, engine = TestBuild(out, ['transfer', parse_param([bytearray(TOKEN_CONTRACT_OWNER), self.wallet_2_script_hash.Data, test_transfer_id])], self.GetWallet1(), '0710', '05')
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].GetBoolean(), True)

        self.assertEqual(len(TestContract.dispatched_events), 4)
        evt = TestContract.dispatched_events[0]
        self.assertIsInstance(evt, NotifyEvent)
        self.assertEqual(evt.addr_from.Data, bytearray(TOKEN_CONTRACT_OWNER))
        self.assertEqual(evt.addr_to, self.wallet_2_script_hash)
        self.assertEqual(evt.amount, 1)
       
        # now get balance of wallet 2
        tx, results, total_ops, engine = TestBuild(out, ['balanceOf', parse_param([self.wallet_2_script_hash.Data])], self.GetWallet1(), '0710', '05')
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].GetBigInteger(), 1)

        # now the owner should have less
        tx, results, total_ops, engine = TestBuild(out, ['balanceOf', parse_param([bytearray(TOKEN_CONTRACT_OWNER)])], self.GetWallet1(), '0710', '05')
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].GetBigInteger(), 0)

        # now this transfer should fail
        tx, results, total_ops, engine = TestBuild(out, ['transfer', parse_param([bytearray(TOKEN_CONTRACT_OWNER), self.wallet_3_script_hash.Data, test_transfer_id])], self.GetWallet1(), '0710', '05')
        self.assertEqual(len(results), 0)

        # this transfer should fail because it is not signed by the 'from' address
        tx, results, total_ops, engine = TestBuild(out, ['transfer', parse_param([bytearray(TOKEN_CONTRACT_OWNER), self.wallet_3_script_hash.Data, 1])], self.GetWallet3(), '0710', '05')
        self.assertEqual(len(results), 0)

        # now this transfer should fail, this is from address with no tokens
        tx, results, total_ops, engine = TestBuild(out, ['transfer', parse_param([self.wallet_3_script_hash.Data, self.wallet_1_script_hash.Data, 1])], self.GetWallet3(), '0710', '05')
        self.assertEqual(len(results), 0)

        # get balance of bad data
        tx, results, total_ops, engine = TestBuild(out, ['balanceOf', parse_param(['abc'])], self.GetWallet1(), '0710', '05')
        self.assertEqual(len(results), 0)

        # get balance no params
        tx, results, total_ops, engine = TestBuild(out, ['balanceOf', parse_param([])], self.GetWallet1(), '0710', '05')
        self.assertEqual(len(results), 0)

    def test_NFT_3_mint(self):

        output = Compiler.instance().load('nft_template.py').default
        out = output.write()

        TestContract.dispatched_events = []

	# mint another token
        owner = bytearray(TOKEN_CONTRACT_OWNER)
        tx, results, total_ops, engine = TestBuild(out, ['mintToken', parse_param([owner,2,'token2ROData','https://example.com/images/2.png','token2ROData'])], self.GetWallet1(), '0710', '05')
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].GetBoolean(), True)

        # it should dispatch an event
        self.assertEqual(len(TestContract.dispatched_events), 8)
        evt = TestContract.dispatched_events[0]
        self.assertIsInstance(evt, NotifyEvent)
        self.assertEqual(evt.addr_to, self.wallet_1_script_hash)

        # now the total circulation should be bigger
        tx, results, total_ops, engine = TestBuild(out, ['totalSupply', '[]'], self.GetWallet1(), '0710', '05')
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].GetBigInteger(), 2)

	# trying to mint a token with an existing token ID should fail
        owner = bytearray(TOKEN_CONTRACT_OWNER)
        tx, results, total_ops, engine = TestBuild(out, ['mintToken', parse_param([owner,2,'token2ROData','https://example.com/images/2.png','token2ROData'])], self.GetWallet1(), '0710', '05')
        self.assertEqual(len(results), 0)


    def test_NFT_4_approval(self):

        output = Compiler.instance().load('nft_template.py').default
        out = output.write()

        # get balance of wallet 2
        tx, results, total_ops, engine = TestBuild(out, ['balanceOf', parse_param([self.wallet_2_script_hash.Data])], self.GetWallet1(), '0710', '05')
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].GetBigInteger(), 1)

        # get owner of token 1
        tx, results, total_ops, engine = TestBuild(out, ['ownerOf', parse_param([1])], self.GetWallet1(), '0710', '05')
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].GetByteArray(), self.wallet_2_script_hash.Data)

        # tranfer_from, approve, allowance
        tx, results, total_ops, engine = TestBuild(out, ['allowance', parse_param([1])], self.GetWallet3(), '0710', '05')
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].GetBigInteger(), 0)

        # try to transfer from
        tx, results, total_ops, engine = TestBuild(out, ['transferFrom', parse_param([self.wallet_2_script_hash.Data, self.wallet_3_script_hash.Data, 1])], self.GetWallet3(), '0710', '05')
        self.assertEqual(len(results), 0)

        # try to approve from someone not yourself
        tx, results, total_ops, engine = TestBuild(out, ['approve', parse_param([self.wallet_2_script_hash.Data, self.wallet_2_script_hash.Data, 1])], self.GetWallet3(), '0710', '05')
        self.assertEqual(len(results), 0)

        # try to approve a token you don't own
        tx, results, total_ops, engine = TestBuild(out, ['approve', parse_param([self.wallet_3_script_hash.Data, self.wallet_2_script_hash.Data, 999999])], self.GetWallet3(), '0710', '05')
        self.assertEqual(len(results), 0)

        TestContract.dispatched_events = []

        # approve should work
        tx, results, total_ops, engine = TestBuild(out, ['approve', parse_param([self.wallet_2_script_hash.Data, self.wallet_3_script_hash.Data, 1])], self.GetWallet2(), '0710', '05')
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].GetBoolean(), True)

        # it should dispatch an event
        self.assertEqual(len(TestContract.dispatched_events), 4)
        evt = TestContract.dispatched_events[0]
        self.assertIsInstance(evt, NotifyEvent)
        self.assertEqual(evt.notify_type, b'approve')
        self.assertEqual(evt.amount, 1)

        # check allowance
        tx, results, total_ops, engine = TestBuild(out, ['allowance', parse_param([1])], self.GetWallet1(), '0710', '05')
        self.assertEqual(len(results), 1)
        self.assertEqual(len(results[0].GetByteArray()), 40)

        # approve should not be additive, it should overwrite previous approvals
        tx, results, total_ops, engine = TestBuild(out, ['approve', parse_param([self.wallet_2_script_hash.Data, self.wallet_3_script_hash.Data, 1])], self.GetWallet2(), '0710', '05')
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].GetBoolean(), True)

        tx, results, total_ops, engine = TestBuild(out, ['allowance', parse_param([1])], self.GetWallet2(), '0710', '05')
        self.assertEqual(len(results), 1)
        self.assertEqual(len(results[0].GetByteArray()), 40)

        # nash-style transferFrom should fail because call is not from a whitelisted DEX
        tx, results, total_ops, engine = TestBuild(out, ['transferFrom', parse_param([self.wallet_2_script_hash.Data, self.wallet_3_script_hash.Data, 1])], self.GetWallet3(), '0710', '05')
        self.assertEqual(len(results), 0)

        # receiver currently should have one token
        tx, results, total_ops, engine = TestBuild(out, ['balanceOf', parse_param([self.wallet_1_script_hash.Data])], self.GetWallet1(), '0710', '05')
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].GetBigInteger(), 1)

        # moonlight-style transferFrom with originator/spender should work
        tx, results, total_ops, engine = TestBuild(out, ['transferFrom', parse_param([self.wallet_3_script_hash.Data, self.wallet_2_script_hash.Data, self.wallet_1_script_hash.Data, 1])], self.GetWallet3(), '0710', '05')
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].GetBoolean(), True)

        # now the receiver should have two tokens

        tx, results, total_ops, engine = TestBuild(out, ['balanceOf', parse_param([self.wallet_1_script_hash.Data])], self.GetWallet1(), '0710', '05')
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].GetBigInteger(), 2)

        # now the previous owner should have no balance

        tx, results, total_ops, engine = TestBuild(out, ['balanceOf', parse_param([self.wallet_2_script_hash.Data])], self.GetWallet1(), '0710', '05')
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].GetBigInteger(), 0)

        # now the allowance should be removed for this token

        tx, results, total_ops, engine = TestBuild(out, ['allowance', parse_param([1])], self.GetWallet2(), '0710', '05')
        self.assertEqual(len(results), 1)
        self.assertEqual(len(results[0].GetByteArray()), 0)

