"""
NEO Non-Fungible Token Smart Contract Template

Authors: Joe Stewart, Jonathan Winter
Email: hal0x2328@splyse.tech, jonathan@splyse.tech
Version: 0.2
Date: 06 August 2018
License: MIT

Based on NEP5 template by Tom Saunders

Compile and deploy with neo-python:
neo> build nft_template.py
neo> import contract nft_template.avm 0710 05 True True False

Example invocation
neo> testinvoke {this_contract_hash} tokensOfOwner [{your_wallet_address}, 0]

# Note: I haven't found any documentation on best practice for when one should use Runtime.Log vs Runtime.Notify,
# so I am using Log for recording changes on the blockchain/events (transfers, approvals, minting, and modifications)
# and Notify for everything else.
"""
from boa.builtins import concat, list
from boa.interop.Neo.Action import RegisterAction
from boa.interop.Neo.App import DynamicAppCall
from boa.interop.Neo.Blockchain import GetContract
# from boa.interop.Neo.Contract import IsPayable
from boa.interop.Neo.Iterator import IterNext, IterKey, IterValue
from boa.interop.Neo.Runtime import GetTrigger, CheckWitness, Log, Notify
from boa.interop.Neo.Storage import GetContext, Get, Put, Delete, Find
from boa.interop.Neo.TriggerType import Application, Verification
from boa.interop.System.ExecutionEngine import GetExecutingScriptHash, GetCallingScriptHash, GetEntryScriptHash

TOKEN_NAME = 'Non-Fungible Token'
TOKEN_SYMBOL = 'NFT'
TOKEN_CIRC_KEY = b'in_circulation'
# TOKEN_DECIMALS = 0  # nft is indivisible

# This is the script hash of the address for the owner of the contract
# This can be found in ``neo-python`` with the wallet open, use ``wallet`` command
# TOKEN_CONTRACT_OWNER = b'+z\x15\xd2\xc6e\xa9\xc3B\xf0jI\x8fW\x13\xa4\x93\x14\xc1\x04' # joe's wallet
TOKEN_CONTRACT_OWNER = b'\x0f\x26\x1f\xe5\xc5\x2c\x6b\x01\xa4\x7b\xbd\x02\xbd\x4d\xd3\x3f\xf1\x88\xc9\xde'

OnApprove = RegisterAction('approve', 'addr_from', 'addr_to', 'amount')
OnNFTApprove = RegisterAction('NFTapprove', 'addr_from', 'addr_to', 'tokenid')
OnTransfer = RegisterAction('transfer', 'addr_from', 'addr_to', 'amount')
OnNFTTransfer = RegisterAction('NFTtransfer', 'addr_from', 'addr_to', 'tokenid')


def Main(operation, args):
	"""
	Entry point to the program

	:param str operation: The name of the operation to perform
	:param list args: A list of arguments along with the operation
	:return: The result of the operation
	:rtype: bytearray

	Token operations:
	- allowance(token_id): returns approved third-party spender of a token
	- approve(token_receiver, token_id, revoke): approve third party to spend a token
	- balanceOf(owner): returns owner's current total tokens owned
	- mintToken(properties, URI, owner, extra_arg): create a new NFT token with the specified properties and URI
	- modifyURI(token_id, token_data): modify specified token's URI data
	- name(): returns name of token
	- ownerOf(token_id): returns the owner of the specified token.
	- postMintContract(): returns the contract that a freshly minted token gets passed to by default
	- supportedStandards(): returns a list of supported standards {"NEP-10", "NEP-5"}
	- symbol(): returns token symbol
	- tokenProperties(token_id): returns a token's read-only data
	- tokensOfOwner(owner, start_index): returns a list that contains ten of the tokens
		owned by the specified address starting at the specified index.
	- tokenURI(token_id): Returns a distinct Uniform Resource Identifier (URI) for a given asset.
		The URI data of a token supplies a reference to get more information about a specific token or its data.
	- totalSupply(): Returns the total token supply deployed in the system.
	- transfer(to, token_id): transfers a token
	- transferFrom(from, to, token_id): allows a third party to execute an approved transfer

	setters
	- setName(name): sets the name of the token
	- setSymbol(symbol): sets the token's symbol
	- setSupportedStandards(supported_standards): sets the supported standards
	- setPostMintContract(contract_address): sets the contract freshly minted tokens get sent to by default
	"""

	trigger = GetTrigger()

	if trigger == Verification():

		if CheckWitness(TOKEN_CONTRACT_OWNER):
			return True

	elif trigger == Application():

		ctx = GetContext()

		# NEP-5 operations
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

		elif operation == 'totalSupply':
			return Get(ctx, TOKEN_CIRC_KEY)

		arg_error = 'incorrect arg length'

		if operation == 'balanceOf':
			if len(args) == 1:
				if len(args[0]) == 20:
					balance = Get(ctx, args[0])
					if balance > 1:
						return balance - 1
					else:
						return balance
				# have to decrement this because the token id's start counting at 0,
				# but the length of token owner's list starts counting at 1, so balanceOf is off by 1.
				# but, decrementing the owner's new_balance causes a bug where each new token added to the owner's list
				# overwrites the previous one.
				Notify('invalid address')
				return False

			Notify(arg_error)
			return False

		elif operation == 'approve':
			if len(args) == 3:
				# GetCallingScriptHash() can't be done within the function because the
				# calling script hash changes depending on where the function is called
				return do_approve(ctx, GetCallingScriptHash(), args[0], args[1], args[2])

			Notify(arg_error)
			return False

		elif operation == 'allowance':
			if len(args) == 1:
				if len(args[0]) == 0:
					args[0] = b'\x00'
				return Get(ctx, concat('approved/', args[0]))

			Notify(arg_error)
			return False

		elif operation == 'transferFrom':
			if len(args) >= 3:
				return do_transfer_from(ctx, args)

			Notify(arg_error)
			return False

		elif operation == 'transfer':
			if len(args) >= 2:
				# GetCallingScriptHash() can't be done within the function because the
				# calling script hash changes depending on where the function is called
				return do_transfer(ctx, GetCallingScriptHash(), args)

			Notify(arg_error)
			return False

		# NFT operations
		elif operation == 'supportedStandards':
			return Get(ctx, 'supportedStandards')

		elif operation == 'postMintContract':
			return Get(ctx, 'postMintContract')

		elif operation == 'tokensOfOwner':
			if len(args) == 2:
				return do_tokens_of_owner(ctx, args[0], args[1])

			Notify(arg_error)
			return False

		elif operation == 'ownerOf':
			if len(args) == 1:
				if len(args[0]) == 0:
					args[0] = b'\x00'
				t_owner = Get(ctx, args[0])
				if len(t_owner) == 20:
					return t_owner

				Notify('token does not exist')
				return False

			Notify(arg_error)
			return False

		elif operation == 'tokenProperties':
			if len(args) == 1:
				if len(args[0]) == 0:
					args[0] = b'\x00'
				return Get(ctx, concat('properties/', args[0]))

			Notify(arg_error)
			return False

		elif operation == 'tokenURI':
			if len(args) == 1:
				if len(args[0]) == 0:
					args[0] = b'\x00'
				return Get(ctx, concat('uri/', args[0]))

			Notify(arg_error)
			return False

		# Administrative operations
		if CheckWitness(TOKEN_CONTRACT_OWNER):
			if operation == 'setName':
				if len(args) == 1:
					return do_set_config(ctx, 'name', args[0])

				Notify(arg_error)
				return False

			elif operation == 'setSymbol':
				if len(args) == 1:
					return do_set_config(ctx, 'symbol', args[0])

				Notify(arg_error)
				return False

			elif operation == 'setSupportedStandards':
				if len(args) == 1:
					return do_set_config(ctx, 'supportedStandards', args[0])

				Notify(arg_error)
				return False

			elif operation == 'setPostMintContract':
				if len(args) == 1:
					if len(args[0]) == 20:
						return do_set_config(ctx, 'postMintContract', args[0])

					Notify('invalid address')
					return False

				Notify(arg_error)
				return False

			elif operation == 'mintToken':
				if len(args) >= 2:
					return do_mint_token(ctx, args)

				Notify(arg_error)
				return False

			elif operation == 'modifyURI':
				if len(args) == 2:
					return do_modify_token(ctx, args[0], args[1])

				Notify(arg_error)
				return False
		else:
			Notify('unauthorized operation')
			return False

		Notify('unknown operation')
	return False


def do_set_config(ctx, key, value):
	"""
	Sets or deletes a config key

	:param StorageContext ctx: current store context
	:param str key: key
	:param value: value
	:return: config success
	:rtype: boolean
	"""
	if len(value) > 0:
		Put(ctx, key, value)
		Log('config key set')
	else:
		Delete(ctx, key)
		Log('config key deleted')
	return True


def do_mint_token(ctx, args):
	"""
	Mints a new NFT token; stores it's properties, URI info, and owner on the blockchain;
	updates the totalSupply

	:param StorageContext ctx: current store context
	:param list args:
		0: t_properties: token's read only data
		1: t_uri: token's uri
		2: t_owner (optional): default is postMintContract, can be a user address, or another smart contract
		3: extra_arg (optional): extra arg to be passed to smart contract
	:return: new total supply of tokens
	:rtype: integer or boolean
	"""
	t_id = Get(ctx, TOKEN_CIRC_KEY)
	if len(t_id) == 0:
		t_id = b'\x00'  # the int 0 is represented as b'' in NEO

	exists = Get(ctx, t_id)  # this should never already exist
	if len(exists) == 20:
		Notify('token already exists')
		return False

	t_properties = args[0]
	if len(t_properties) == 0:
		Notify('missing properties data string')
		return False

	t_uri = args[1]

	# if nft contract owner passed a third argument,
	# check if it is a user/contract address, if so set t_owner to the specified address
	t_owner = b''
	if len(args) > 2:
		if len(args[2]) == 20:
			t_owner = args[2]

	# if nft contract owner didn't pass an address, transfer the newly minted token to the default contract.
	# if nft contract owner did pass an address and it is a smart contract, transfer the newly minted token
	# to the passed contract
	this_contract = GetExecutingScriptHash()
	if len(t_owner) != 20:
		t_owner = Get(ctx, 'postMintContract')
		contract_args = [this_contract, t_owner, t_id]
		if len(args) == 3:  # append optional extra_arg
			contract_args.append(args[2])
		success = transfer_to_smart_contract(ctx, contract_args, True)
		if success is False:
			return False
	elif len(t_owner) == 20:  # for some strange reason, neo-boa compiler throws and error when this
		if GetContract(t_owner):  # is 'and' with this
			contract_args = [this_contract, t_owner, t_id]
			if len(args) == 4:  # append optional extra arg
				contract_args.append(args[3])
			success = transfer_to_smart_contract(ctx, contract_args, True)
			if success is False:
				return False

	Put(ctx, t_id, t_owner)  # update token's owner
	Put(ctx, concat('properties/', t_id), t_properties)  # propkey = concat('prop/', t_id)
	Put(ctx, concat('uri/', t_id), t_uri)  # urikey = concat('uri/', t_id)

	add_token_to_owners_list(ctx, t_owner, t_id)

	new_total_supply = t_id + 1
	Put(ctx, TOKEN_CIRC_KEY, new_total_supply)  # update total supply
	Log(concat('total supply updated: ', new_total_supply))
	return new_total_supply


def do_modify_token(ctx, t_id, t_data):
	"""
	Modifies token URI

	:param StorageContext ctx: current store context
	:param bytes t_id: token id
	:param bytes t_data: token data
	:return: URI modification success
	:rtype: boolean
	"""
	if len(t_id) == 0:
		t_id = b'\x00'  # the int 0 is represented as b'' in NEO

	exists = Get(ctx, t_id)
	if len(exists) != 20:
		Notify('token does not exist')
		return False

	Put(ctx, concat('uri/', t_id), t_data)  # urikey = concat('uri/', t_id)
	Log('token uri has been updated')
	return True


def do_tokens_of_owner(ctx, t_owner, start_index):
	"""
	This method returns ten of the owner's tokens starting at the given index. The index is used for paginating
	through the results. The index is needed for the situation where the owner's list of tokens could be quite large.

	For example, the specified owner could have 100,000 tokens out of 1,000,000 minted tokens. In such a scenario,
	returning the full list of token id's would be quite expensive and could possibly be too large to return anyway.
	Hence, @hal0x2328 recognized the need to paginate the data in such a scenario.
	So, if we know that this user has a balanceOf() 100,000 tokens and we want to get their 10 most recent tokens,
	then our call would be like so: `testinvoke {my_hash} tokensOfOwner [{owner address string}, 999990]`
	The string version of the result would look something like:
	"\x03, \xc8, \xd0\x07, \x04, )\x02, i\x86\x01, \x95\xc4\x00, \x8c\x1e, \x811\x01, \x17, "

	:param StorageContext ctx: current store context
	:param bytes t_owner: token owner
	:param bytes start_index: the index to start searching through the owner's tokens
	:return: list of tokens
	:rtype: string or boolean
	"""
	if len(t_owner) == 20:
		if len(start_index) == 0:
			start_index = b'\x01'

		start_key = concat(t_owner, start_index)
		count = 0  # counter to make sure that the returned tokens string doesn't get too large
		tokens = ''
		token_iter = Find(ctx, t_owner)
		# while loop explained: keep looping through the owner's list of tokens until 10 have been found
		# beginning at the starting index.
		# if statement explained: once a key has been found matching my search key (or of greater value),
		# append the token id to the string, increment the counter, and disregard trying to find a
		# matching key thereafter.
		# (once a key has been found matching my search key (or greater),
		# just get everything afterward while count < 10)
		while (token_iter.IterNext()) and (count < 10):
			if (token_iter.IterKey() >= start_key) or (count > 0):
				tokens = concat(tokens, concat(token_iter.IterValue(), ', '))
				count += 1

		Notify(concat("Ten of owner's tokens: ", tokens))
		return tokens

	Notify('invalid address')
	return False


def do_approve(ctx, caller, t_receiver, t_id, revoke):
	"""
	Approve a token to eventually be transferred to the t_receiver

	:param StorageContext ctx: current store context
	:param bytes caller: calling script hash
	:param bytes t_receiver: address of the future token owner
	:param bytes t_id: int: token id
	:param bytes revoke: set to 1 to revoke previous approval
	:return: approval success
	:rtype: boolean
	"""
	if len(t_receiver) != 20:
		Notify('invalid address')
		return False

	if len(t_id) == 0:
		t_id = b'\x00'

	if len(revoke) == 0:
		revoke = 0

	t_owner = Get(ctx, t_id)
	if len(t_owner) != 20:
		Notify('token does not exist')
		return False

	if t_owner == t_receiver:
		Notify('approved spend to self!')
		return True

	is_token_owner = CheckWitness(t_owner)

	if is_token_owner and GetEntryScriptHash() != caller:
		Notify('third party script is bouncing the signature to us')
		return False  # A third party script is bouncing the signature to us
	# if token owner is a smart contract and is the calling script hash, continue
	elif GetContract(t_owner) and t_owner == caller:
		is_token_owner = True

	if is_token_owner:
		approval_key = concat('approved/', t_id)
		if revoke != 0:
			Delete(ctx, approval_key)

			OnApprove(t_owner, t_receiver, 0)  # For backward compatibility with blockchain trackers
			OnNFTApprove(t_owner, '', t_id)

			Log('previous token approval revoked')
			return True

		Put(ctx, approval_key, concat(t_owner, t_receiver))  # approved_spend = concat(t_owner, t_receiver)

		OnApprove(t_owner, t_receiver, 1)  # For backward compatibility with blockchain trackers
		OnNFTApprove(t_owner, t_receiver, t_id)  # actual approval action

		Log('token approved for transfer')
		return True

	Notify('incorrect permission')
	return False


def do_transfer_from(ctx, args):
	"""
	Transfers the approved token at the specified id from the t_from address to the t_to address

	:param StorageContext ctx: current store context
	:param list args:
		0: t_from: transfer from address (token owner)
		1: t_to: transfer to address (token receiver)
		2: t_id: token id
		3: extra_arg: optional argument that can be passed (for use only with smart contracts)
	:return: transferFrom success
	:rtype: boolean
	"""
	t_from = args[0]
	t_to = args[1]
	t_id = args[2]

	if len(t_from) != 20 or len(t_to) != 20:
		Notify('invalid address')
		return False

	if t_from == t_to:
		Notify('transfer to self!')
		return True

	if len(t_id) == 0:
		t_id = b'\x00'  # the int 0 is represented as b'' in NEO

	t_owner = Get(ctx, t_id)
	if len(t_owner) != 20:
		Notify('token does not exist')
		return False

	if t_from != t_owner:
		Notify('from address is not the owner of this token')
		return False

	approval_key = concat('approved/', t_id)
	authorized_spend = Get(ctx, approval_key)  # value returned is concat(t_owner, t_receiver)

	# len(t_owner) = 20 and len(t_spender) = 20, thus the length of authorized_spender should be 40
	if len(authorized_spend) != 40:
		Notify('no approval exists for this token')
		return False

	# if the input transfer from and transfer to addresses match the authorized spend
	if authorized_spend == concat(t_from, t_to):
		# is t_to a smart contract? If yes, invoke its onTokenTransfer
		# operation to let it know tokens are being sent - if it returns
		# False then reject the transfer
		if GetContract(t_to):
			success = transfer_to_smart_contract(ctx, args, False)
			if success is False:
				return False
		else:
			# if t_to is not a contract, there shouldn't be any
			# extra args to transfer(), this could be a phishing
			# attempt so reject the transfer
			if len(args) > 3:
				Notify('incorrect arg length')
				return False

		if authorized_spend == concat(t_from, t_to):
			res = remove_token_from_owners_list(ctx, t_from, t_id)
			if res is False:
				Notify('unable to transfer token')
				return False

			Put(ctx, t_id, t_to)  # record token's new owner
			Delete(ctx, approval_key)  # remove the approval for this token
			add_token_to_owners_list(ctx, t_to, t_id)

			OnTransfer(t_from, t_to, 1)  # For backward compatibility with blockchain trackers
			OnNFTTransfer(t_from, t_to, t_id)  # actual transfer action

			Log('transfer complete')
			return True

	Notify('spend not approved')
	return False


def do_transfer(ctx, caller, args):
	"""
	Transfers a token at the specified id from the t_owner address to the t_to address

	:param StorageContext ctx: current store context
	:param bytes caller: calling script hash
	:param list args:
		0: t_to: transfer to address
		1: t_id: token id
		2: extra_arg: optional argument that can be passed (for use only with smart contracts)
	:return: transfer success
	:rtype: boolean
	"""
	t_to = args[0]
	t_id = args[1]

	if len(t_to) != 20:
		Notify('invalid address')
		return False

	if len(t_id) == 0:
		t_id = b'\x00'  # the int 0 is represented as b'' in NEO

	t_owner = Get(ctx, t_id)
	if len(t_owner) != 20:
		Notify('token does not exist')
		return False

	if t_owner == t_to:
		Notify('transfer to self!')
		return True

	# Verifies that the calling contract has verified the required script hashes of the transaction/block
	is_token_owner = CheckWitness(t_owner)

	if is_token_owner and GetEntryScriptHash() != caller:
		Notify('third party script is bouncing the signature to us')
		return False  # A third party script is bouncing the signature to us
	# if token owner is a smart contract and is the calling script hash, continue
	elif GetContract(t_owner) and t_owner == caller:
		is_token_owner = True

	if is_token_owner:
		# is t_to a smart contract? If yes, invoke its onTokenTransfer
		# operation to let it know tokens are being sent - if it returns
		# False then reject the transfer
		if GetContract(t_to):
			contract_args = [t_owner, t_to, t_id]
			if len(args) > 2:
				contract_args.append(args[2])
			success = transfer_to_smart_contract(ctx, contract_args, False)
			if success is False:
				return False
		else:
			# if t_to is not a contract, there shouldn't be any
			# extra args to transfer(), this could be a phishing
			# attempt so reject the transfer
			if len(args) > 2:
				Notify('incorrect arg length')
				return False

		res = remove_token_from_owners_list(ctx, t_owner, t_id)
		if res is False:
			Notify('unable to transfer token')
			return False

		Put(ctx, t_id, t_to)  # update token's owner
		Delete(ctx, concat('approved/', t_id))  # remove any existing approvals for this token
		add_token_to_owners_list(ctx, t_to, t_id)

		OnTransfer(t_owner, t_to, 1)  # always only transferring one NFT at a time, backwards compatibility
		OnNFTTransfer(t_owner, t_to, t_id)  # the actual transfer action

		Log('transfer complete')
		return True

	Notify('tx sender is not the token owner')
	return False


def remove_token_from_owners_list(ctx, t_owner, t_id):
	"""
	Removes a token from owner's list of tokens

	:param StorageContext ctx: current store context
	:param bytes t_owner: token owner
	:param bytes t_id: token id
	:return: token removal success
	:rtype: boolean
	"""
	length = Get(ctx, t_owner)  # get how many tokens this owner owns
	if len(length) == 0:  # this should be impossible, but just in case, leaving it here
		Notify('owner has no tokens')
		return False

	if len(t_id) == 0:
		t_id = b'\x00'

	token_iter = Find(ctx, t_owner)  # finds all of these tokens whose keys are prefixed with t_owner
	while token_iter.IterNext():  # each token should be a tuple represented like so: (b'key', b'value')
		if token_iter.IterValue() == t_id:
			Delete(ctx, token_iter.IterKey())
			new_balance = length - 1
			if new_balance > 0:  # if the owner has more than 0 tokens, store their new token balance
				Put(ctx, t_owner, new_balance)
			else:  # else remove the owner from storage
				Delete(ctx, t_owner)

			Log("removed token from owner's list and decremented owner's balance")
			return True

	Notify("token not found in owner's list")
	return False


def add_token_to_owners_list(ctx, t_owner, t_id):
	"""
	Adds a token to the owner's list of tokens

	:param StorageContext ctx: current store context
	:param bytes t_owner: token owner (could be either a smart contract or a wallet address)
	:param bytes t_id: token ID
	:return: token id
	:rtype: integer
	"""
	length = Get(ctx, t_owner)  # number of these tokens the owner has
	if len(length) == 0:
		length = 1
	# Note: length is set to b'\x01' because the 0th token ends up being overwritten in storage by
	# Put(ctx, t_owner, new_balance) when length = 0
	# length starts at b'\x01' instead of b'\x00' because something like b'\x05\x00' is equal to b'\x05',
	# meaning that it messes with the `if (token_iter.IterKey() >= start_key)` part of do_tokens_of_owner() by
	# causing a bug where the first element returned is the number of elements in the array.

	# Note: the storage array keeping track of the owner's list of tokens starts counting at b'\x01',
	# but token id's start counting at b'\x00'

	if len(t_id) == 0:
		t_id = b'\x00'

	Put(ctx, concat(t_owner, length), t_id)  # store owner's tokens
	new_balance = length + 1  # neo-boa compiler allows arithmetic addition between bytes and int
	Put(ctx, t_owner, new_balance)  # store owner's new balance
	Log("added token to owner's list and incremented owner's balance")
	return t_id


def transfer_to_smart_contract(ctx, args, is_mint):
	"""
	Transfers a token to a smart contract

	:param StorageContext ctx: current store context
	:param list args:
		0: transfer from address (who is sending the NFT)
		1: transfer to address (who is receiving the NFT)
		2: token id
		3: extra_arg (optional)
	:param bool is_mint: whether or not the token is being minted
	:return: transfer success
	:rtype: boolean
	"""
	t_from = args[0]
	t_to = args[1]
	t_id = args[2]

	if len(t_from) != 20 or len(t_to) != 20:
		Notify('invalid address')
		return False

	if len(t_id) == 0:
		t_id = b'\x00'
		args[2] = b'\x00'
	# is t_to a smart contract? If yes, invoke its onTokenTransfer
	# operation to let it know tokens are being sent - if it returns
	# False then reject the transfer
	success = DynamicAppCall(t_to, 'onNFTTransfer', args)
	if success is False:
		Notify('transfer rejected by recipient contract')
		return False

	# need to check funds again in case a transfer or approval
	# change happened inside the onTokenTransfer call
	# the is_mint check is needed b/c you can't get the token owner for a token that hasn't finished being minted yet
	if is_mint is False:
		t_owner = Get(ctx, t_id)
		if t_owner != t_from:
			Notify('insufficient funds')
			return False

	Log('transfer accepted by recipient contract')
	return True
