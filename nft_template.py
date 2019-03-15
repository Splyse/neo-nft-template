"""NEO Non-Fungible Token Smart Contract Template

Authors: Joe Stewart, Jonathan Winter
Email: hal0x2328@splyse.tech, jonathan@splyse.tech
Version: 2.0
Date: 15 March 2019
License: MIT

Based on NEP5 template by Tom Saunders

Example test using neo-local:
neo> sc build_run /smart-contracts/nft_template.py test 0710 05 True False False name []

Compile and import with neo-python using neo-local:
neo> sc build /smart-contracts/nft_template.py
neo> sc deploy /smart-contracts/nft_template.avm 0710 05 True False False

Example invocation
neo> testinvoke {this_contract_hash} tokensOfOwner [{your_wallet_address}, 1]

"""

from boa.builtins import concat
from boa.interop.Neo.Action import RegisterAction
from boa.interop.Neo.App import DynamicAppCall
from boa.interop.Neo.Blockchain import GetContract
from boa.interop.Neo.Iterator import Iterator
from boa.interop.Neo.Runtime import (CheckWitness, GetTrigger, Log,
                                     Notify, Serialize)
from boa.interop.Neo.Storage import GetContext, Get, Put, Delete, Find
from boa.interop.Neo.TriggerType import Application, Verification
from boa.interop.System.ExecutionEngine import (GetCallingScriptHash,
                                                GetEntryScriptHash,
                                                GetExecutingScriptHash)

# This is the script hash of the address for the owner of the contract
# This can be found in ``neo-python`` with the wallet open,
# use ``wallet`` command
TOKEN_CONTRACT_OWNER = b'\x1c\xc9\xc0\\\xef\xff\xe6\xcd\xd7\xb1\x82\x81j\x91R\xec!\x8d.\xc0'
DAPP_ADMIN = b'\x08t/\\P5\xac-\x0b\x1c\xb4\x94tIyBu\x7f1*' # can set RW properties
TOKEN_NAME = 'Non-Fungible Token Template'
TOKEN_SYMBOL = 'NFT'
TOKEN_DECIMALS = 0
TOKEN_CIRC_KEY = b'in_circulation'

# Smart Contract Event Notifications
OnApprove = RegisterAction('approve', 'addr_from', 'addr_to', 'amount')
OnNFTApprove = RegisterAction('NFTapprove', 'addr_from', 'addr_to', 'tokenid')
OnTransfer = RegisterAction('transfer', 'addr_from', 'addr_to', 'amount')
OnNFTTransfer = RegisterAction('NFTtransfer', 'addr_from', 'addr_to', 'tokenid')
OnMint = RegisterAction('mint', 'addr_to', 'amount')
OnNFTMint = RegisterAction('NFTmint', 'addr_to', 'tokenid')
OnError = RegisterAction('error', 'message')

# common errors
ARG_ERROR = 'incorrect arg length'
INVALID_ADDRESS_ERROR = 'invalid address'
PERMISSION_ERROR = 'incorrect permission'
TOKEN_DNE_ERROR = 'token does not exist'


def Main(operation, args):
    """Entry point to the program

    :param str operation: The name of the operation to perform
    :param list args: A list of arguments along with the operation
    :return: The result of the operation
    :rtype: bytearray

    Token operations:
    - allowance(token_id): returns approved third-party spender of a
        token
    - approve(token_receiver, token_id, revoke): approve third party
        to spend a token
    - balanceOf(owner): returns owner's current total tokens owned
    - name(): returns name of token
    - decimals(): returns token decimal precision
    - ownerOf(token_id): returns the owner of the specified token.
    - properties(token_id): returns a token's read-only data
    - rwProperties(token_id): returns a token's read/write data
    - supportedStandards(): returns a list of supported standards
        {"NEP-10"}
    - symbol(): returns token symbol
    - token(token_id): returns a dictionary where token, property,
        and uri keys map to the corresponding data for the given
        `token_id`
    - tokensOfOwner(owner, starting_index): returns a dictionary that
        contains less than or equal to ten of the tokens owned by
        the specified address starting at the `starting_index`.
    - totalSupply(): Returns the total token supply deployed in the
        system.
    - transfer(to, token_id, extra_arg): transfers a token
    - transferFrom(spender, from, to, token_id): allows a third party
        to execute a pre-approved transfer
    - uri(token_id): Returns a distinct Uniform Resource Identifier
        (URI) for a given asset.
        The URI data of a token supplies a reference to get more
        information about a specific token or its data.

    TOKEN_CONTRACT_OWNER operations:
        - mintToken(owner, properties, URI, extra_arg): create a new
            NFT token with the specified properties and URI and send it
            to the specified owner
        - modifyURI(token_id, token_data): modify specified token's
            URI data

        setters:
        - setName(name): sets the name of the token
        - setSymbol(symbol): sets the token's symbol
        - setSupportedStandards(supported_standards): sets the
            supported standards, 'NEP-10' is always the first element
            in the array
    """
    # The trigger determines whether this smart contract is being run
    # in 'verification' mode or 'application'
    trigger = GetTrigger()

    # 'Verification' mode is used when trying to spend assets
    # (eg NEO, Gas) on behalf of this contract's address
    if trigger == Verification():

        # if the script that sent this is the owner, we allow the spend
        if CheckWitness(TOKEN_CONTRACT_OWNER):
            return True

    elif trigger == Application():

        # Need to get this at the top level
        caller = GetCallingScriptHash()
        ctx = GetContext()

        if operation == 'name':
            name = Get(ctx, 'name')
            if name:
                return name
            else:
                return TOKEN_NAME

        elif operation == 'symbol':
            symbol = Get(ctx, 'symbol')
            if symbol:
                return symbol
            else:
                return TOKEN_SYMBOL

        elif operation == 'supportedStandards':
            supported_standards = Get(ctx, 'supportedStandards')
            if supported_standards:
                return supported_standards
            else:
                return Serialize(['NEP-10'])

        elif operation == 'totalSupply':
            return Get(ctx, TOKEN_CIRC_KEY)

        elif operation == 'allowance':
            assert len(args) == 1, ARG_ERROR
            ownership = safe_deserialize(Get(ctx, concat('ownership/', args[0])))
            assert ownership, TOKEN_DNE_ERROR
            # don't fault here in case a calling contract is just checking allowance value
            if not has_key(ownership, 'approved'): return False
            if len(ownership['approved']) != 40: return False
            return ownership['approved']

        elif operation == 'balanceOf':
            assert len(args) == 1, ARG_ERROR
            assert len(args[0]) == 20, INVALID_ADDRESS_ERROR
            token_iter = Find(ctx, args[0])
            count = 0
            while token_iter.next():
                count += 1
            return count

        elif operation == 'ownerOf':
            assert len(args) == 1, ARG_ERROR
            ownership = safe_deserialize(Get(ctx, concat('ownership/', args[0])))
            assert ownership, TOKEN_DNE_ERROR
            assert has_key(ownership, 'owner'), TOKEN_DNE_ERROR
            assert len(ownership['owner']) == 20, TOKEN_DNE_ERROR
            return ownership['owner']

        elif operation == 'properties':
            assert len(args) == 1, ARG_ERROR
            return get_properties(ctx, args[0])

        elif operation == 'rwProperties':
            assert len(args) == 1, ARG_ERROR
            return get_rw_properties(ctx, args[0])

        elif operation == 'token':
            assert len(args) == 1, ARG_ERROR
            token = Get(ctx, concat('token/', args[0]))
            assert token, TOKEN_DNE_ERROR
            return token

        elif operation == 'tokensOfOwner':
            assert len(args) == 2, ARG_ERROR
            tokens_of_owner = do_tokens_of_owner(ctx, args[0], args[1])
            assert tokens_of_owner, 'address has no tokens'
            return Serialize(tokens_of_owner)

        elif operation == 'uri':
            assert len(args) == 1, ARG_ERROR
            token = safe_deserialize(Get(ctx, concat('token/', args[0])))
            assert token, TOKEN_DNE_ERROR
            assert has_key(token, 'uri'), TOKEN_DNE_ERROR
            return token['uri']

        elif operation == 'decimals':
            return TOKEN_DECIMALS

        #
        # User RW operations
        #

        if operation == 'approve':
            # args: from, spender, id, revoke
            # (NFT needs a fourth argument to revoke approval)
            assert len(args) > 2, ARG_ERROR
            assert args[2], TOKEN_DNE_ERROR 
            return do_approve(ctx, caller, args)

        elif operation == 'transfer':
            assert len(args) > 1, ARG_ERROR
            return do_transfer(ctx, caller, args)

        elif operation == 'transferFrom':

            assert len(args) > 2, ARG_ERROR
            if len(args) == 3:
                # Nash-style (from, to, amount/id) transferFrom that can 
                # be invoked only by whitelisted DEX to initiate a 
                # pre-approved transfer

                return nash_do_transfer_from(ctx, caller, args)
            else:
                # Moonlight-style (spender, from, to, amount/id)
                # transfer where an authenticated spender/originator is 
                # the only one who can initiate a transfer but can send 
                # to an arbitrary third party (or themselves)

                return do_transfer_from(ctx, caller, args)

        #
        # dApp operations
        #
        if operation == 'setRWProperties':
            # args: token id, rwdata
            assert CheckWitness(DAPP_ADMIN), PERMISSION_ERROR
            assert len(args) == 2, ARG_ERROR
            return set_rw_properties(ctx, args[0], args[1])


        # Administrative operations
        if CheckWitness(TOKEN_CONTRACT_OWNER):
            if operation == 'mintToken':
                assert len(args) > 3, ARG_ERROR
                return do_mint_token(ctx, args)

            elif operation == 'modifyURI':
                assert len(args) == 2, ARG_ERROR
                return do_modify_uri(ctx, args) 

            elif operation == 'setName':
                assert len(args) == 1, ARG_ERROR
                return do_set_config(ctx, 'name', args[0])

            elif operation == 'setSymbol':
                assert len(args) == 1, ARG_ERROR
                return do_set_config(ctx, 'symbol', args[0])

            elif operation == 'setSupportedStandards':
                assert len(args) >= 1, ARG_ERROR
                supported_standards = ['NEP-10']
                for arg in args:
                    supported_standards.append(arg)
                return do_set_config(ctx, 'supportedStandards', Serialize(supported_standards))

        AssertionError('unknown operation')
    return False


def do_approve(ctx, Caller, args):
    """Approve a token to be transferred to a third party by an approved spender

    :param StorageContext ctx: current store context
    :param bytearray t_owner: current owner of the token
    :param bytearray t_spender: spender to approve
    :param int t_id: int: token id
    :param bool revoke: set to True to revoke previous approval
    :return: approval success
    :rtype: bool
    """
    t_owner = args[0]
    t_spender = args[1]
    t_id = args[2]
    revoke = False

    if len(args) > 3:
        revoke = args[3] 
    
    if Caller != GetEntryScriptHash() and not is_whitelisted_dex(ctx, Caller):
        # non-whitelisted contracts can only approve their own funds for transfer,
        # even if they have the signature of the owner on the invocation 
        t_owner = Caller

    assert len(t_owner) == 20, INVALID_ADDRESS_ERROR
    assert len(t_spender) == 20, INVALID_ADDRESS_ERROR
    assert t_id, TOKEN_DNE_ERROR

    ownership_key = concat('ownership/', t_id)
    ownership = safe_deserialize(Get(ctx, ownership_key))

    assert ownership, TOKEN_DNE_ERROR
    assert has_key(ownership, 'owner'), TOKEN_DNE_ERROR
    assert t_owner == ownership['owner'], PERMISSION_ERROR
    assert t_owner != t_spender, 'same owner and spender'
    assert authenticate(t_owner, Caller), PERMISSION_ERROR

    # revoke previous approval if revoke is True
    if revoke:
        if has_key(ownership, 'approved'):
            ownership.remove('approved')
            Put(ctx, ownership_key, Serialize(ownership))

        # log the revoking of previous approvals
        OnApprove(t_owner, t_spender, 0)
        OnNFTApprove(t_owner, '', t_id)
        return True

    ownership['approved'] = concat(t_owner, t_spender)
    # approve this transfer
    Put(ctx, ownership_key, Serialize(ownership))
    # Log this approval event
    OnApprove(t_owner, t_spender, 1)
    OnNFTApprove(t_owner, t_spender, t_id)
    return True

def do_mint_token(ctx, args):
    """Mints a new NFT token; stores it's properties, URI info, and
    owner on the blockchain; updates the totalSupply

    :param StorageContext ctx: current store context
    :param list args:
        0: bytearray t_owner: token owner
        1: int t_id: token id (must not already exist)
        2: str t_properties: token's read only data
        3: str t_uri: token's uri
        4: str t_rw_properties: token's read/write data (optional)
    :return: mint success
    :rtype: bool
    """

    t_circ = Get(ctx, TOKEN_CIRC_KEY)
    t_circ += 1

    assert len(args[0]) == 20, INVALID_ADDRESS_ERROR
    assert args[1], 'missing token id'
    assert args[2], 'missing properties'
    assert args[3], 'missing uri'

    t_id = args[1]
    token = safe_deserialize(Get(ctx, concat('token/', t_id)))
    assert not token, 'token already exists'

    # basically a token 'object' containing the token's
    # id, uri, and properties
    token = {}
    ownership = {}  # information about the token's owner

    token['id'] = t_id
    token['uri'] = args[3]
    token['properties'] = args[2] # this can never change

    if len(args) > 4:
        token['rwproperties'] = args[4]
    else:
        token['rwproperties'] = ''

    ownership['owner'] = args[0]

    Put(ctx, concat('token/', t_id), Serialize(token))
    # update token's owner
    Put(ctx, concat('ownership/', t_id), Serialize(ownership))
    res = add_token_to_owners_list(ctx, ownership['owner'], t_id)
    Put(ctx, TOKEN_CIRC_KEY, t_circ)  # update total supply
    # Log this minting event
    OnTransfer('', ownership['owner'], 1)
    OnNFTTransfer('', ownership['owner'], t_id)
    OnMint(ownership['owner'], 1)
    OnNFTMint(ownership['owner'], t_id)
    return True


def do_modify_uri(ctx, args):
    """Modifies token URI

    :param StorageContext ctx: current store context
    :param int t_id: token id
    :param str t_uri: token uri
    :return: URI modification success
    :rtype: bool
    """

    t_id = args[0]
    t_uri = args[1]

    token_key = concat('token/', t_id)
    token = safe_deserialize(Get(ctx, token_key))
    assert token, TOKEN_DNE_ERROR

    token['uri'] = t_uri
    Put(ctx, token_key, Serialize(token))
    return True


def do_tokens_of_owner(ctx, t_owner, start_id):
    """This method returns ten of the owner's tokens starting at the
    given index. The index is used for paginating through the results.
    Pagination is needed for the situation where the owner's dict of
    tokens could be quite large.

    :param StorageContext ctx: current store context
    :param bytearray t_owner: token owner
    :param int start_id: the id to start searching through the
        owner's tokens
    :return: dictionary of id, properties, and uri keys mapped to their
        corresponding token's data
    :rtype: bool or dict
    """

    assert len(t_owner) == 20, INVALID_ADDRESS_ERROR 

    if start_id == 0:
        start_id = 1  # token id's cannot go below 1

    start_key = concat(t_owner, start_id)
    count = 0
    token_dict = {}
    token_iter = Find(ctx, t_owner)

    # while loop explained: keep looping through the owner's list
    # of tokens until 10 have been found beginning at the starting
    # index.
    # if statement explained: once a key has been found matching
    # my search key (or of greater value),
    # update the dictionary, increment the counter,
    # and disregard trying to find a matching key thereafter.
    # (once a key has been found matching my search key
    # (or greater), just get everything afterward while count < 10)

    while token_iter.next() and (count < 10):
        if (token_iter.Key >= start_key) or (count > 0):
            token_key = concat('token/', token_iter.Value)
            token = safe_deserialize(Get(ctx, token_key))
            if token:
                token_dict[token_key] = token
                count += 1
    return token_dict


def do_transfer(ctx, Caller, args):
    """Transfers a token at the specified id from the t_owner address
    to the t_to address

    :param StorageContext ctx: current store context
    :param list args:
        0: bytearray t_to: transfer to address
        1: int t_id: token id
    :return: transfer success
    :rtype: bool
    """
    # we don't need the t_from because the token data stores the owner
    t_from = ""
    t_to = args[0]
    t_id = args[1]

    if len(args) == 3:  # use traditional from, to, id format if they want to send it
        t_from = args[0]
        t_to = args[1]
        t_id = args[2]

    if Caller != GetEntryScriptHash() and not is_whitelisted_dex(ctx, Caller):
        # non-whitelisted contracts can only approve their own funds for transfer,
        # even if they have the signature of the owner on the invocation 
        t_from = Caller

    assert len(t_to) == 20, INVALID_ADDRESS_ERROR 
    ownership = safe_deserialize(Get(ctx, concat('ownership/', t_id)))

    assert ownership, TOKEN_DNE_ERROR
    assert has_key(ownership, 'owner'), TOKEN_DNE_ERROR
    assert len(ownership['owner']) == 20, TOKEN_DNE_ERROR

    t_owner = ownership['owner']

    if t_owner == t_to:
        print('transfer to self')
        return True

    assert authenticate(t_owner, Caller), PERMISSION_ERROR

    res = remove_token_from_owners_list(ctx, t_owner, t_id)
    assert res, 'unable to remove token from owner list'
   
    ownership['owner'] = t_to  # update token's owner
    # remove any existing approvals for this token
    if has_key(ownership, 'approved'):
        ownership.remove('approved')

    Put(ctx, concat('ownership/', t_id), Serialize(ownership))
    res = add_token_to_owners_list(ctx, t_to, t_id)

    # log this transfer event
    OnTransfer(t_owner, t_to, 1)
    OnNFTTransfer(t_owner, t_to, t_id)
    return True

def do_transfer_from(ctx, Caller, args):
    """Transfers the approved token at the specified id from the
    t_from address to the t_to address

    Only the approved spender OR a whitelisted DEX can invoke this function
    and a whitelisted DEX will still need to pass the authentication of the spender

    :param StorageContext ctx: current store context
    :param list args:
        0: bytearray t_spender: approved spender address
        1: bytearray t_from: transfer from address (token owner)
        2: bytearray t_to: transfer to address (token receiver)
        3: int t_id: token id
    :return: transferFrom success
    :rtype: bool
    """

    t_spender = args[0]
    t_from = args[1]
    t_to = args[2]
    t_id = args[3]

    if Caller != GetEntryScriptHash() and not is_whitelisted_dex(ctx, Caller):
        # non-whitelisted contracts can only approve their own funds for transfer,
        # even if they have the signature of the owner on the invocation 
        t_from = Caller

    assert len(t_spender) == 20, INVALID_ADDRESS_ERROR 
    assert len(t_from) == 20, INVALID_ADDRESS_ERROR 
    assert len(t_to) == 20, INVALID_ADDRESS_ERROR 
    assert authenticate(t_spender, Caller), PERMISSION_ERROR

    if t_from == t_to:
        print('transfer to self')
        return True

    ownership = safe_deserialize(Get(ctx, concat('ownership/', t_id)))
    assert ownership, TOKEN_DNE_ERROR
    assert has_key(ownership, 'owner'), TOKEN_DNE_ERROR
    assert has_key(ownership, 'approved'), 'no approval exists for this token'
    assert len(ownership['owner']) == 20, TOKEN_DNE_ERROR

    t_owner = ownership['owner']

    assert t_from == t_owner, 'from address is not the owner of this token'
    assert len(ownership['approved']) == 40, 'malformed approval key for this token'

    # Finally check to see if the owner approved this spender
    assert ownership['approved'] == concat(t_from, t_spender), PERMISSION_ERROR

    res = remove_token_from_owners_list(ctx, t_from, t_id)
    assert res, 'unable to remove token from owner list'

    ownership['owner'] = t_to
    ownership.remove('approved')  # remove previous approval
    Put(ctx, concat('ownership/', t_id), Serialize(ownership))
    res = add_token_to_owners_list(ctx, t_to, t_id)

    # log this transfer event
    OnTransfer(t_from, t_to, 1)
    OnNFTTransfer(t_from, t_to, t_id)
    return True


def nash_do_transfer_from(ctx, Caller, args):
    """Transfers the approved token at the specified id from the
    t_from address to the t_to address

    Only a whitelisted DEX can invoke this function

    :param StorageContext ctx: current store context
    :param list args:
        0: bytearray t_from: transfer from address (token owner)
        1: bytearray t_to: transfer to address (token receiver)
        2: int t_id: token id
    :return: transferFrom success
    :rtype: bool
    """

    t_from = args[0]
    t_to = args[1]
    t_id = args[2]

    assert is_whitelisted_dex(ctx, Caller), PERMISSION_ERROR
    assert len(t_from) == 20, INVALID_ADDRESS_ERROR 
    assert len(t_to) == 20, INVALID_ADDRESS_ERROR 
            
    if t_from == t_to:
        print('transfer to self')
        return True

    ownership = safe_deserialize(Get(ctx, concat('ownership/', t_id)))
    assert ownership, TOKEN_DNE_ERROR
    assert has_key(ownership, 'owner'), TOKEN_DNE_ERROR
    assert has_key(ownership, 'approved'), 'no approval exists for this token'
    assert len(ownership['owner']) == 20, TOKEN_DNE_ERROR

    t_owner = ownership['owner']

    assert t_from == t_owner, 'from address is not the owner of this token'
    assert len(ownership['approved']) == 40, 'malformed approval key for this token'

    assert ownership['approved'] == concat(t_from, t_to), PERMISSION_ERROR

    res = remove_token_from_owners_list(ctx, t_from, t_id)
    assert res, 'unable to remove token from owner list'

    ownership['owner'] = t_to
    ownership.remove('approved')  # remove previous approval
    Put(ctx, concat('ownership/', t_id), Serialize(ownership))
    res = add_token_to_owners_list(ctx, t_to, t_id)

    # log this transfer event
    OnTransfer(t_from, t_to, 1)
    OnNFTTransfer(t_from, t_to, t_id)
    return True


# helper methods
def do_set_config(ctx, key, value):
    """Sets or deletes a config key

    :param StorageContext ctx: current store context
    :param str key: key
    :param any value: value
    :return: config success
    :rtype: bool
    """
    if len(value) > 0:
        Put(ctx, key, value)
        print('config key set')
    else:
        Delete(ctx, key)
        print('config key deleted')

    return True


def safe_deserialize(data):
    """Checks to see if the data exists before attempting to
    deserialize it

    :param list or dict data: data to deserialize
    :return: deserialized data or False
    :rtype: bool or list or dict
    """

    if data:
        obj = Deserialize(data)
        return obj
    return False


def add_token_to_owners_list(ctx, t_owner, t_id):
    """Adds a token to the owner's list of tokens

    :param StorageContext ctx: current store context
    :param bytearray t_owner: token owner (could be either a smart
        contract or a wallet address)
    :param int t_id: token ID
    :return: none
    """
    Put(ctx, concat(t_owner, t_id), t_id)  # store owner's new token
    return True


def remove_token_from_owners_list(ctx, t_owner, t_id):
    """Removes a token from owner's list of tokens

    :param StorageContext ctx: current store context
    :param bytearray t_owner: token owner
    :param int t_id: token id
    :return: successfully removed token from owner's list
    :rtype: bool
    """
    ckey = concat(t_owner, t_id)
    if Get(ctx, ckey):
        Delete(ctx, ckey)
        return True

    print("token not found in owner's list")
    return False


def get_properties(ctx, id):
    token = safe_deserialize(Get(ctx, concat('token/', id)))
    if not token:  
        print(TOKEN_DNE_ERROR)
        return False
    if not has_key(token, 'properties'):
        return False
    return token['properties']


def get_rw_properties(ctx, id):
    token = safe_deserialize(Get(ctx, concat('token/', id)))
    if not token:  
        print(TOKEN_DNE_ERROR)
        return False
    if not has_key(token, 'rwproperties'):
        return False
    return token['rwproperties']


def set_rw_properties(ctx, id, data):
    token_key = concat('token/', id)
    token = safe_deserialize(Get(ctx, token_key ))

    if not token:
        print(TOKEN_DNE_ERROR)
        return False
    token['rwproperties'] = data
    Put(ctx, token_key, Serialize(token))
    return True


def authenticate(scripthash, Caller):
    if CheckWitness(scripthash): return True
    if GetContract(scripthash) and scripthash == Caller: return True
    return False


def do_whitelist_dex(ctx, args):
    return do_set_config(ctx, concat('exchange/', args[0]), args[1])


def is_whitelisted_dex(ctx, scripthash):
    return Get(ctx, concat('exchange/', scripthash))


def AssertionError(msg):
    OnError(msg) # for neo-cli ApplicationLog
    raise Exception(msg)

