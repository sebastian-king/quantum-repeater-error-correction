#
# Copyright (c) 2017, Stephanie Wehner and Axel Dahlberg
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
# 3. All advertising materials mentioning features or use of this software
#    must display the following acknowledgement:
#    This product includes software developed by Stephanie Wehner, QuTech.
# 4. Neither the name of the QuTech organization nor the
#    names of its contributors may be used to endorse or promote products
#    derived from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDER ''AS IS'' AND ANY
# EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.


import logging
import os

from simulaqron.local.setup import setup_local
from simulaqron.general.hostConfig import socketsConfig
from simulaqron.toolbox import get_simulaqron_path
from twisted.internet.defer import inlineCallbacks
from twisted.spread import pb

from qutip import Qobj


#####################################################################################################
#
# runClientNode
#
# This will be run on the local node if all communication links are set up (to the virtual node
# quantum backend, as well as the nodes in the classical communication network), and the local classical
# communication server is running (if applicable).
#
def runClientNode(qReg, virtRoot, myName, classicalNet):
    """
    Code to execture for the local client node. Called if all connections are established.

    Arguments
    qReg        quantum register (twisted object supporting remote method calls)
    virtRoot    virtual quantum ndoe (twisted object supporting remote method calls)
    myName        name of this node (string)
    classicalNet    servers in the classical communication network (dictionary of hosts)
    """

    logging.debug("LOCAL %s: Runing client side program.", myName)


#####################################################################################################
#
# localNode
#
# This will be run if the local node acts as a server on the classical communication network,
# accepting remote method calls from the other nodes.


class localNode(pb.Root):
    def __init__(self, node, classicalNet):

        self.node = node
        self.classicalNet = classicalNet

        self.virtRoot = None
        self.qReg = None

    def set_virtual_node(self, virtRoot):
        self.virtRoot = virtRoot

    def set_virtual_reg(self, qReg):
        self.qReg = qReg

    def remote_test(self):
        return "Tested!"

    # This can be called by Alice to tell Bob to process the qubit
    @inlineCallbacks
    def remote_process_qubit(self, virtualNum):
        """
        Recover the qubit and measure it to get a random number.

        Arguments
        virtualNum    number of the virtual qubit corresponding to the EPR pair received
        """

        qB = yield self.virtRoot.callRemote("get_virtual_ref", virtualNum)

	# Entanglement swap
	# Create 2 qubits
        qC = yield self.virtRoot.callRemote("new_qubit_inreg", self.qReg)
        qD = yield self.virtRoot.callRemote("new_qubit_inreg", self.qReg)
        # Entangle qC and qD
        yield qC.callRemote("apply_H")
        yield qC.callRemote("cnot_onto", qD)
        # Un-make EPR pair of Alice's qB and repeater's qC
        yield qB.callRemote("cnot_onto", qC)
        yield qB.callRemote("apply_H")
        print("REPEATER3: Entanglement has been swapped\n")

        # Measure qB and qC
        x = yield qB.callRemote("measure", True)
        y = yield qC.callRemote("measure", True)

        # Send ACK to source, using classical network
        # The source machine can correct the Z phase by using the measurement we sent
        alice = self.classicalNet.hostDict["Alice"]
        yield alice.root.callRemote("repeater_ack", y)
        print("REPEATER3: Sent ACK to source over classical network")

        if (y): # If qC is ON then apply a CNOT date to qD
            yield qC.callRemote("cnot_onto", qD)

        # Send the qubit to the next node
        remoteNum = yield self.virtRoot.callRemote("send_qubit", qD, "Bob")
        bob = self.classicalNet.hostDict["Bob"]
        yield bob.root.callRemote("process_qubit", remoteNum)

        print("REPEATER3: Forwarded qubit to next node over quantum network\n")

    def assemble_qubit(self, realM, imagM):
        """
        Reconstitute the qubit as a qutip object from its real and imaginary components given as a list.
        We need this since Twisted PB does not support sending complex valued object natively.
        """
        M = realM
        for s in range(len(M)):
            for t in range(len(M)):
                M[s][t] = realM[s][t] + 1j * imagM[s][t]

        return Qobj(M)


#####################################################################################################
#
# main
#
def main():

    # In this example, we are Bob.
    myName = "Repeater3"

    # This file defines the network of virtual quantum nodes
    simulaqron_path = get_simulaqron_path.main()
    virtualFile = os.path.join(simulaqron_path, "config/virtualNodes.cfg")

    # This file defines the nodes acting as servers in the classical communication network
    classicalFile = "repeater3_classical_net.cfg"

    # Read configuration files for the virtual quantum, as well as the classical network
    virtualNet = socketsConfig(virtualFile)
    classicalNet = socketsConfig(classicalFile)

    # Check if we should run a local classical server. If so, initialize the code
    # to handle remote connections on the classical communication network
    if myName in classicalNet.hostDict:
        lNode = localNode(classicalNet.hostDict[myName], classicalNet)
        logging.debug("LOCAL %s: Initialise a classical server..: %s.", myName, lNode)
    else:
        lNode = None
        logging.debug("LOCAL %s: No initialisation of classical server..: %s.", myName, lNode)

        # Set up the local classical server if applicable, and connect to the virtual
        # node and other classical servers. Once all connections are set up, this will
        # execute the function runClientNode
    setup_local(myName, virtualNet, classicalNet, lNode, runClientNode)


##################################################################################################
logging.basicConfig(format="%(asctime)s:%(levelname)s:%(message)s", level=logging.DEBUG)
main()
