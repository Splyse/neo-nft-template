"""NEO Non-Fungible Token Smart Contract Template

Authors: Joe Stewart, Jonathan Winter
Email: hal0x2328@splyse.tech, jonathan@splyse.tech
Version: 1.0
Date: 02 October 2018
License: MIT

Based on NEP5 template by Tom Saunders

Example test using neo-local:
neo> build /smart-contracts/nft_template.py test 0710 05 True True False name []

Compile and deploy with neo-python:
neo> build nft_template.py
neo> import contract nft_template.avm 0710 05 True True False

Example invocation
neo> testinvoke {this_contract_hash} tokensOfOwner [{your_wallet_address}, 0]

# Note: I haven't found any documentation on best practice for when
one should use Runtime.Log vs Runtime.Notify, so I am using Log
for recording changes on the blockchain that aren't covered by the
SmartContract Event Notifications (primarily config changes) and
Notify for everything else.
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
# TOKEN_CONTRACT_OWNER = b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
# TOKEN_CONTRACT_OWNER = b'\x0f&\x1f\xe5\xc5,k\x01\xa4{\xbd\x02\xbdM\xd3?\xf1\x88\xc9\xde'
TOKEN_CONTRACT_OWNER = b'#\xba\'\x03\xc52c\xe8\xd6\xe5"\xdc2 39\xdc\xd8\xee\xe9'
TOKEN_NAME = 'Non-Fungible Token Template'
TOKEN_SYMBOL = 'NFT'
TOKEN_CIRC_KEY = b'in_circulation'

# Smart Contract Event Notifications
OnApprove = RegisterAction('approve', 'addr_from', 'addr_to', 'amount')
OnNFTApprove = RegisterAction('NFTapprove', 'addr_from', 'addr_to', 'tokenid')
OnTransfer = RegisterAction('transfer', 'addr_from', 'addr_to', 'amount')
OnNFTTransfer = RegisterAction('NFTtransfer', 'addr_from', 'addr_to', 'tokenid')
OnMint = RegisterAction('mint', 'addr_to', 'amount')
OnNFTMint = RegisterAction('NFTmint', 'addr_to', 'tokenid')

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
    - ownerOf(token_id): returns the owner of the specified token.
    - properties(token_id): returns a token's read-only data
    - supportedStandards(): returns a list of supported standards
        {"NEP-10"}
    - symbol(): returns token symbol
    - tokenData(token_id): returns a dictionary where token, property,
        and uri keys map to the corresponding data for the given
        `token_id`
    - tokensDataOfOwner(owner, starting_index): returns a dictionary
        that contains less than or equal to five of the tokens (where
        token, properties, and uri keys map to their corresponding data
        for each token id) owned by the specified address starting at
        the `starting_index`.
    - tokensOfOwner(owner, starting_index): returns a list that
        contains less than or equal to ten of the tokens owned by
        the specified address starting at the `starting_index`.
    - totalSupply(): Returns the total token supply deployed in the
        system.
    - transfer(to, token_id, extra_arg): transfers a token
    - transferFrom(from, to, token_id, extra_arg): allows a third party to
        execute an approved transfer
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
            supported standards, 'NEP-10' must be the first element
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

        if operation == 'allowance':
            if len(args) == 1:
                return Get(ctx, concat('approved/', args[0]))

            Notify(ARG_ERROR)
            return False

        elif operation == 'approve':
            if len(args) == 3:
                # GetCallingScriptHash() can't be done within the
                # function because the calling script hash changes
                # depending on where the function is called
                return do_approve(ctx, GetCallingScriptHash(), args[0], args[1], args[2])

            Notify(ARG_ERROR)
            return False

        elif operation == 'balanceOf':
            if len(args) == 1:
                if len(args[0]) == 20:
                    return Get(ctx, args[0])

                Notify(INVALID_ADDRESS_ERROR)
                return False

            Notify(ARG_ERROR)
            return False

        elif operation == 'ownerOf':
            if len(args) == 1:
                t_owner = Get(ctx, args[0])
                if len(t_owner) == 20:
                    return t_owner

                Notify(TOKEN_DNE_ERROR)
                return False

            Notify(ARG_ERROR)
            return False

        elif operation == 'properties':
            if len(args) == 1:
                token_properties = Get(ctx, concat('properties/', args[0]))
                if token_properties:
                    return token_properties

                Notify(TOKEN_DNE_ERROR)
                return False

            Notify(ARG_ERROR)
            return False

        elif operation == 'tokenData':
            if len(args) == 1:
                # check to make sure the token exists
                if len(Get(ctx, args[0])) == 20:
                    return Serialize(do_token_data(ctx, args[0]))

                Notify(TOKEN_DNE_ERROR)
                return False

            Notify(ARG_ERROR)
            return False

        elif operation == 'tokensDataOfOwner':
            if len(args) == 2:
                tokens_data_of_owner = do_tokens_data_of_owner(ctx, args[0], args[1])
                if tokens_data_of_owner:
                    return Serialize(tokens_data_of_owner)

                return False

            Notify(ARG_ERROR)
            return False

        elif operation == 'tokensOfOwner':
            if len(args) == 2:
                tokens_of_owner = do_tokens_of_owner(ctx, args[0], args[1])
                if tokens_of_owner:
                    return Serialize(tokens_of_owner)

                return False

            Notify(ARG_ERROR)
            return False

        elif operation == 'transfer':
            if len(args) >= 2:
                # GetCallingScriptHash() can't be done within the
                # function because the calling script hash changes
                # depending on where the function is called
                return do_transfer(ctx, GetCallingScriptHash(), args)

            Notify(ARG_ERROR)
            return False

        elif operation == 'transferFrom':
            if len(args) >= 3:
                return do_transfer_from(ctx, args)

            Notify(ARG_ERROR)
            return False

        elif operation == 'uri':
            if len(args) == 1:
                token_uri = Get(ctx, concat('uri/', args[0]))
                if token_uri:
                    return token_uri

                Notify(TOKEN_DNE_ERROR)
                return False

            Notify(ARG_ERROR)
            return False

        # Administrative operations
        if CheckWitness(TOKEN_CONTRACT_OWNER):
            if operation == 'mintToken':
                if len(args) >= 3:
                    return do_mint_token(ctx, args)

                Notify(ARG_ERROR)
                return False

            elif operation == 'modifyURI':
                if len(args) == 2:
                    return do_modify_uri(ctx, args[0], args[1])

                Notify(ARG_ERROR)
                return False

            elif operation == 'setName':
                if len(args) == 1:
                    return do_set_config(ctx, 'name', args[0])

                Notify(ARG_ERROR)
                return False

            elif operation == 'setSymbol':
                if len(args) == 1:
                    return do_set_config(ctx, 'symbol', args[0])

                Notify(ARG_ERROR)
                return False

            elif operation == 'setSupportedStandards':
                if len(args) >= 1:
                    if args[0] == 'NEP-10':
                        return do_set_config(ctx, 'supportedStandards', Serialize(args))

                    Notify('NEP-10 must be the first arg')
                    return False

                Notify(ARG_ERROR)
                return False

        else:
            Notify(PERMISSION_ERROR)
            return False

        Notify('unknown operation')

    return False


def do_approve(ctx, caller, t_receiver, t_id, revoke):
    """Approve a token to eventually be transferred to the t_receiver

    :param StorageContext ctx: current store context
    :param byte[] caller: calling script hash
    :param byte[] t_receiver: address of the future token owner
    :param bytes t_id: int: token id
    :param bytes revoke: set to 1 to revoke previous approval
    :return: approval success
    :rtype: bool
    """
    if len(t_receiver) != 20:
        Notify(INVALID_ADDRESS_ERROR)
        return False

    if len(revoke) == b'\x00':
        revoke = b'\x00'

    t_owner = Get(ctx, t_id)
    if len(t_owner) != 20:
        Notify(TOKEN_DNE_ERROR)
        return False

    if t_owner == t_receiver:
        Notify('approved spend to self')
        return True

    is_token_owner = CheckWitness(t_owner)
    if is_token_owner and GetEntryScriptHash() != caller:
        Notify('third party script is bouncing the signature to us')
        return False
    # if token owner is a smart contract and is the calling
    # script hash, continue
    elif GetContract(t_owner) and t_owner == caller:
        is_token_owner = True

    if is_token_owner:
        approval_key = concat('approved/', t_id)
        # revoke previous approval if revoke != 0
        if revoke != b'\x00':
            Delete(ctx, approval_key)
            # log the revoking of previous approvals
            OnApprove(t_owner, t_receiver, b'\x00')
            OnNFTApprove(t_owner, '', t_id)
            return True

        # approve this transfer
        Put(ctx, approval_key, concat(t_owner, t_receiver))

        # Log this approval event
        OnApprove(t_owner, t_receiver, 1)
        OnNFTApprove(t_owner, t_receiver, t_id)
        return True

    Notify(PERMISSION_ERROR)
    return False


def do_mint_token(ctx, args):
    """Mints a new NFT token; stores it's properties, URI info, and
    owner on the blockchain; updates the totalSupply

    :param StorageContext ctx: current store context
    :param list args:
        0: byte[] t_owner: token owner
        1: byte[] t_properties: token's read only data
        2: bytes t_uri: token's uri
        3: extra_arg (optional): extra arg to be passed to a smart
            contract
    :return: mint success
    :rtype: bool
    """
    t_id = Get(ctx, TOKEN_CIRC_KEY)
    # the int 0 is represented as b'' in neo-boa, this caused bugs
    # throughout my code
    # This is the reason why token id's start at 1 instead
    t_id += 1

    # this should never already exist
    if len(Get(ctx, t_id)) == 20:
        Notify('token already exists')
        return False
    
    t_owner = args[0]
    if len(t_owner) != 20:
        Notify(INVALID_ADDRESS_ERROR)
        return False

    t_properties = args[1]
    if len(t_properties) == b'\x00':
        Notify('missing properties data string')
        return False

    t_uri = args[2]

    if GetContract(t_owner):
        contract_args = [t_owner, t_id]
        if len(args) == 4:  # append optional extra arg
            contract_args.append(args[3])

        success = transfer_to_smart_contract(ctx, GetExecutingScriptHash(), contract_args, True)
        if success is False:
            return False

    Put(ctx, t_id, t_owner)  # update token's owner
    Put(ctx, concat('properties/', t_id), t_properties)
    Put(ctx, concat('uri/', t_id), t_uri)
    add_token_to_owners_list(ctx, t_owner, t_id)
    Put(ctx, TOKEN_CIRC_KEY, t_id)  # update total supply

    # Log this minting event
    OnMint(t_owner, 1)
    OnNFTMint(t_owner, t_id)
    return True


def do_modify_uri(ctx, t_id, t_uri):
    """Modifies token URI

    :param StorageContext ctx: current store context
    :param bytes t_id: token id
    :param bytes t_uri: token uri
    :return: URI modification success
    :rtype: bool
    """
    if len(Get(ctx, t_id)) != 20:
        Notify(TOKEN_DNE_ERROR)
        return False

    Put(ctx, concat('uri/', t_id), t_uri)
    Log('token uri has been updated')
    return True


def do_tokens_data_of_owner(ctx, t_owner, start_index):
    """This method returns five of the owner's token's id and
    data starting at the given index.
    See `do_tokens_of_owner` for more detailed information behind
    rationale.

    :param StorageContext ctx: current store context
    :param byte[] t_owner: token owner
    :param bytes start_index: the index to start searching through the
        owner's tokens
    :return: dictionary of id, properties, and uri keys mapped to their
        corresponding token's data
    :rtype: bool or dict
    """
    if len(t_owner) != 20:
        Notify(INVALID_ADDRESS_ERROR)
        return False

    if len(start_index) == b'\x00':
        start_index = b'\x01'  # token id's cannot go below 1

    start_key = concat(t_owner, start_index)
    count = 0
    token_dict = {}
    token_iter = Find(ctx, t_owner)
    # while loop explained: keep looping through the owner's list
    # of tokens until 5 have been found beginning at the starting
    # index.
    # if statement explained: once a key has been found matching
    # my search key (or of greater value),
    # add the token id to the dictionary along with its data,
    # increment the counter,
    # and disregard trying to find a matching key thereafter.
    # (once a key has been found matching my search key
    # (or greater), just get everything afterward while count < 5)
    while token_iter.next() and (count < 5):
        if (token_iter.Key >= start_key) or (count > 0):
            token_data = do_token_data(ctx, token_iter.Value)
            # keys
            token_key = concat('token/', token_iter.Value)
            prop_key = concat('properties/', token_iter.Value)
            uri_key = concat('uri/', token_iter.Value)

            # update dictionary
            token_dict[token_key] = token_data[token_key]
            token_dict[prop_key] = token_data[prop_key]
            token_dict[uri_key] = token_data[uri_key]

            count += 1

    if len(token_dict) >= 1:
        return token_dict

    Notify(TOKEN_DNE_ERROR)
    return False


def do_tokens_of_owner(ctx, t_owner, start_index):
    """This method returns ten of the owner's tokens starting at the
    given index. The index is used for paginating through the results.
    Pagination is needed for the situation where the owner's list of
    tokens could be quite large.

    For example, the specified owner could have 100,000 tokens out
    of 1,000,000 minted tokens.
    In such a scenario, returning the full list of token id's would
    be quite expensive and could possibly be too large to return anyway.
    Hence, @hal0x2328 recognized the need to paginate the
    data in such a scenario. So, if we know that this user has a
    balanceOf() 100,000 tokens and we want to get their 10 most recent
    tokens, then our call would be like so:
    `testinvoke {my_hash} tokensOfOwner [{owner address string}, 999990]`
    The results would look something like:
        [{'type': 'ByteArray',
        'value':
        '800a00010100010200010300010400010500010600010700010800010900010a'}]

    :param StorageContext ctx: current store context
    :param byte[] t_owner: token owner
    :param bytes start_index: the index to start searching through the
        owner's tokens
    :return: list of tokens
    :rtype: bool or list
    """
    if len(t_owner) != 20:
        Notify(INVALID_ADDRESS_ERROR)
        return False

    if len(start_index) == b'\x00':
        start_index = b'\x01'  # token id's cannot go below 1

    start_key = concat(t_owner, start_index)
    count = 0
    token_list = []
    token_iter = Find(ctx, t_owner)
    # while loop explained: keep looping through the owner's list
    # of tokens until 10 have been found beginning at the starting
    # index.
    # if statement explained: once a key has been found matching
    # my search key (or of greater value),
    # append the token id to the list, increment the counter,
    # and disregard trying to find a matching key thereafter.
    # (once a key has been found matching my search key
    # (or greater), just get everything afterward while count < 10)
    while token_iter.next() and (count < 10):
        if (token_iter.Key >= start_key) or (count > 0):
            token_list.append(token_iter.Value)
            count += 1

    if len(token_list) >= 1:
        return token_list

    Notify(TOKEN_DNE_ERROR)
    return False


def do_transfer(ctx, caller, args):
    """Transfers a token at the specified id from the t_owner address
    to the t_to address

    :param StorageContext ctx: current store context
    :param bytes caller: calling script hash
    :param list args:
        0: byte[] t_to: transfer to address
        1: bytes t_id: token id
        2: extra_arg: optional argument that can be passed (for use
            only with smart contracts)
    :return: transfer success
    :rtype: bool
    """
    t_to = args[0]
    t_id = args[1]

    if len(t_to) != 20:
        Notify(INVALID_ADDRESS_ERROR)
        return False

    t_owner = Get(ctx, t_id)
    if len(t_owner) != 20:
        Notify(TOKEN_DNE_ERROR)
        return False

    if t_owner == t_to:
        Notify('transfer to self')
        return True

    # Verifies that the calling contract has verified the required
    # script hashes of the transaction/block
    is_token_owner = CheckWitness(t_owner)
    if is_token_owner and GetEntryScriptHash() != caller:
        Notify('third party script is bouncing the signature to us')
        return False
    # if token owner is a smart contract and is the calling
    # script hash, continue
    elif GetContract(t_owner) and t_owner == caller:
        is_token_owner = True

    if is_token_owner:
        # 1. Is t_to a smart contract?
        # If True, invoke the transfer_to_smart_contract
        # method, if transfer_to_smart_contract() returns False,
        # then reject the transfer
        if GetContract(t_to):
            success = transfer_to_smart_contract(ctx, t_owner, args, False)
            if success is False:
                return False
        else:
            if len(args) > 2:
                Notify(ARG_ERROR)
                return False

        res = remove_token_from_owners_list(ctx, t_owner, t_id)
        if res is False:
            Notify('unable to transfer token')
            return False

        Put(ctx, t_id, t_to)  # update token's owner
        # remove any existing approvals for this token
        Delete(ctx, concat('approved/', t_id))
        add_token_to_owners_list(ctx, t_to, t_id)

        # log this transfer event
        OnTransfer(t_owner, t_to, 1)
        OnNFTTransfer(t_owner, t_to, t_id)
        return True

    Notify(PERMISSION_ERROR)
    return False


def do_transfer_from(ctx, args):
    """Transfers the approved token at the specified id from the
    t_from address to the t_to address

    :param StorageContext ctx: current store context
    :param list args:
        0: byte[] t_from: transfer from address (token owner)
        1: byte[] t_to: transfer to address (token receiver)
        2: bytes t_id: token id
        3: extra_arg: optional argument that can be passed (for use
            only with smart contracts)
    :return: transferFrom success
    :rtype: bool
    """
    t_from = args[0]
    t_to = args[1]
    t_id = args[2]

    if len(t_from) != 20 or len(t_to) != 20:
        Notify(INVALID_ADDRESS_ERROR)
        return False

    if t_from == t_to:
        Notify('transfer to self')
        return True

    t_owner = Get(ctx, t_id)
    if len(t_owner) != 20:
        Notify(TOKEN_DNE_ERROR)
        return False

    if t_from != t_owner:
        Notify('from address is not the owner of this token')
        return False

    approval_key = concat('approved/', t_id)
    # authorized spend should be concat(t_owner, t_receiver)
    authorized_spend = Get(ctx, approval_key)

    # len(t_owner) == 20 and len(t_receiver) == 20, thus the length of
    # authorized_spender should be 40
    if len(authorized_spend) != 40:
        Notify('no approval exists for this token')
        return False

    # if the input transfer from and transfer to addresses match the
    # authorized spend
    if authorized_spend == concat(t_from, t_to):
        # 1. Is t_to a smart contract?
        # If True, invoke the transfer_to_smart_contract method.
        # if transfer_to_smart_contract() returns False, then
        # reject the transfer
        if GetContract(t_to):
            args.remove(0)
            success = transfer_to_smart_contract(ctx, t_from, args, False)
            if success is False:
                return False
        else:
            # if t_to is not a contract, there shouldn't be any
            # extra args to transfer(), this could be a phishing
            # attempt so reject the transfer
            if len(args) > 3:
                Notify(ARG_ERROR)
                return False

        res = remove_token_from_owners_list(ctx, t_from, t_id)
        if res is False:
            Notify('unable to transfer token')
            return False

        Put(ctx, t_id, t_to)  # record token's new owner
        Delete(ctx, approval_key)  # remove previous approval
        add_token_to_owners_list(ctx, t_to, t_id)

        # log this transfer event
        OnTransfer(t_from, t_to, 1)
        OnNFTTransfer(t_from, t_to, t_id)
        return True

    Notify(PERMISSION_ERROR)
    return False


# helper methods
def do_set_config(ctx, key, value):
    """Sets or deletes a config key

    :param StorageContext ctx: current store context
    :param str key: key
    :param value: value
    :return: config success
    :rtype: bool
    """
    if len(value) > 0:
        Put(ctx, key, value)
        Log('config key set')
    else:
        Delete(ctx, key)
        Log('config key deleted')

    return True


def do_token_data(ctx, t_id):
    """Returns the specified token's id, properties and uri data
    as a dict

    :param StorageContext ctx: current store context
    :param bytes t_id: token id
    :return: dictionary of id, property, and uri keys mapped to their
        corresponding token's data
    :rtype: dict
    """
    # `token_key` may seem a bit redundant, however I realized that
    # smart contract developers need an easy way to get an
    # integer/bytes data type for the token id to make getting/adding
    # extra data pertaining to a particular token id easier.
    # Otherwise, they would have to parse the uri or properties key to
    # get the token id and then convert that to an integer (which I'm
    # not sure can be done in neo-boa) or do a call to tokensOfOwner
    # keys
    # token_key = concat('token/', t_id)
    prop_key = concat('properties/', t_id)
    uri_key = concat('uri/', t_id)

    token_data = {
        concat('token/', t_id): t_id,
        prop_key: Get(ctx, prop_key),
        uri_key: Get(ctx, uri_key)
    }
    return token_data


def add_token_to_owners_list(ctx, t_owner, t_id):
    """Adds a token to the owner's list of tokens

    :param StorageContext ctx: current store context
    :param byte[] t_owner: token owner (could be either a smart
        contract or a wallet address)
    :param bytes t_id: token ID
    :return: successfully added token to owner's list
    :rtype: bool
    """
    length = Get(ctx, t_owner)  # number of tokens the owner has
    Put(ctx, concat(t_owner, t_id), t_id)  # store owner's new token
    length += 1  # increment the owner's balance
    Put(ctx, t_owner, length)  # store owner's new balance
    Log("added token to owner's list and incremented owner's balance")
    return True


def remove_token_from_owners_list(ctx, t_owner, t_id):
    """Removes a token from owner's list of tokens

    :param StorageContext ctx: current store context
    :param byte[] t_owner: token owner
    :param bytes t_id: token id
    :return: token removal success
    :rtype: bool
    """
    length = Get(ctx, t_owner)  # get how many tokens this owner owns
    # this should be impossible, but just in case, leaving it here
    if len(length) == b'\x00':
        Notify('owner has no tokens')
        return False

    # if Delete returns True, that means the token was
    # successfully deleted and we should decrement the owner's balance.
    # otherwise, the token didn't exist/didn't belong to the owner,
    # so Delete returns False in that case.
    if Delete(ctx, concat(t_owner, t_id)):
        new_balance = length - 1
        if new_balance > 0:
            Put(ctx, t_owner, new_balance)
        else:
            Delete(ctx, t_owner)

        Log("removed token from owner's list and decremented owner's balance")
        return True

    Notify("token not found in owner's list")
    return False


def transfer_to_smart_contract(ctx, t_from, args, is_mint):
    """Transfers a token to a smart contract and triggers the
    receiving contract's onNFTTransfer event.

    :param StorageContext ctx: current store context
    :param byte[] t_from: transfer from address (who is sending the NFT)
    :param list args:
        0: byte[] t_to: transfer to address (who is receiving the NFT)
        1: bytes t_id: token id
        2: extra_arg (optional)
    :param bool is_mint: whether or not the token is being minted
    :return: transfer success
    :rtype: bool
    """
    t_to = args[0]
    t_id = args[1]

    if len(t_from) != 20 or len(t_to) != 20:
        Notify(INVALID_ADDRESS_ERROR)
        return False

    # invoke the onNFTTransfer operation of the recipient contract,
    # if it returns False, then reject the transfer
    success = DynamicAppCall(t_to, 'onNFTTransfer', args)

    if success is False:
        Notify('transfer rejected by recipient contract')
        return False

    # need to check funds again in case a transfer or approval
    # change happened inside the onTokenTransfer call
    # the `is_mint` check is needed because you can't get the token
    # owner for a token that hasn't finished being minted yet
    if is_mint is False:
        t_owner = Get(ctx, t_id)
        if t_owner != t_from:
            Notify('insufficient funds')
            return False

    Log('transfer accepted by recipient contract')
    return True
